#include "handler/dependency_manager.h"
#include "handler/action_engine.h"
#include "handler/artifact_backup.h"
#include "handler/history.h"
#include "handler/transaction.h"
#include "handler/state_paths.h"

#include <fstream>
#include <cctype>
#include <iostream>
#include <regex>
#include <string>
#include <unordered_map>
#include <set>
#include <sstream>

namespace handler {

namespace {
void collectSimpleLines(const std::filesystem::path& file,
                        std::vector<std::string>& out) {
    std::ifstream input(file);
    if (!input) return;
    std::string line;
    while (std::getline(input, line)) {
        if (line.empty() || line[0] == '#') continue;
        out.push_back(line);
    }
}
}

DependencyInfo inspectDependencies(const std::filesystem::path& root,
                                   const std::string& type) {
    DependencyInfo info;
    info.ecosystem = type;

    if (type == "Python" && std::filesystem::exists(root / "requirements.txt")) {
        info.manifest = "requirements.txt";
        collectSimpleLines(root / "requirements.txt", info.declared);
    } else if (type == "Node.js" &&
               std::filesystem::exists(root / "package.json")) {
        info.manifest = "package.json";
        std::ifstream input(root / "package.json");
        std::string line;
        const std::regex dependencyLine(
            R"DELIM(^\s*"([^"]+)"\s*:\s*"([^"]+)")DELIM");
        while (std::getline(input, line)) {
            std::smatch match;
            if (std::regex_search(line, match, dependencyLine))
                info.declared.push_back(match[1].str() + " " + match[2].str());
        }
    } else if (type == "Rust" &&
               std::filesystem::exists(root / "Cargo.toml")) {
        info.manifest = "Cargo.toml";
        collectSimpleLines(root / "Cargo.toml", info.declared);
    } else if (type == "Go" && std::filesystem::exists(root / "go.mod")) {
        info.manifest = "go.mod";
        collectSimpleLines(root / "go.mod", info.declared);
    } else if (type == "C/C++" &&
               std::filesystem::exists(root / "CMakeLists.txt")) {
        info.manifest = "CMakeLists.txt";
    }
    return info;
}

void printDependencies(const DependencyInfo& info) {
    if (info.manifest.empty()) {
        std::cout << "Dependency inspection: no supported manifest found.\n";
        return;
    }
    std::cout << "Dependency inspection [" << info.ecosystem
              << "] via " << info.manifest << ":\n";
    for (const auto& dep : info.declared)
        std::cout << "  " << dep << '\n';
    if (info.declared.empty())
        std::cout << "  No dependency entries parsed by the current lightweight scanner.\n";
}


std::vector<DependencyRequirement> parseDependencyRequirements(const DependencyInfo& info) {
    std::vector<DependencyRequirement> out;
    for (const auto& raw : info.declared) {
        std::string line = raw;
        while (!line.empty() && (line.front() == ' ' || line.front() == '\t')) line.erase(line.begin());
        if (line.empty() || line[0] == '#' || line[0] == '[') continue;
        const auto pos = line.find_first_of("=<>!~ ");
        const std::string name = pos == std::string::npos ? line : line.substr(0, pos);
        std::string constraint = pos == std::string::npos ? "*" : line.substr(pos);
        if (!name.empty()) out.push_back({name, constraint, true});
    }
    return out;
}

std::vector<DependencyConflict> findDependencyConflicts(
    const std::vector<DependencyRequirement>& requirements) {
    std::unordered_map<std::string, std::vector<std::string>> grouped;
    for (const auto& r : requirements) grouped[r.name].push_back(r.constraint);
    std::vector<DependencyConflict> out;
    for (const auto& [name, constraints] : grouped) {
        if (constraints.size() > 1 && !dependencyConstraintsCompatible(constraints))
            out.push_back({name, constraints.front(), constraints.back(),
                           "no version satisfies the combined constraints"});
    }
    return out;
}

std::vector<DependencyCandidate> proposeDependencyUpgrades(
    const std::vector<DependencyRequirement>& requirements) {
    std::vector<DependencyCandidate> out;
    for (const auto& r : requirements) {
        const bool compatible = dependencyConstraintsCompatible({r.constraint});
        out.push_back({r.name, "unknown", r.constraint,
                       compatible ? "REVIEW" : "BLOCKED",
                       compatible ? "registry lookup required before changing the manifest"
                                  : "constraint is internally unsatisfiable", {}, {}});
    }
    return out;
}

void printDependencyAnalysis(const std::vector<DependencyConflict>& conflicts,
                             const std::vector<DependencyCandidate>& candidates) {
    std::cout << "Dependency analysis:\n";
    std::cout << "  Conflicts: " << conflicts.size() << "\n";
    for (const auto& c : conflicts)
        std::cout << "    [CONFLICT] " << c.name << ": " << c.left
                  << " vs " << c.right << " | " << c.reason << "\n";
    std::cout << "  Upgrade candidates: " << candidates.size() << "\n";
    for (const auto& c : candidates)
        std::cout << "    [" << c.action << "] " << c.name
                  << " " << c.constraint << " | " << c.reason << "\n";
}


namespace {
std::string depTrim(std::string s) {
    const auto first=s.find_first_not_of(" \t\r\n");
    if(first==std::string::npos) return {};
    const auto last=s.find_last_not_of(" \t\r\n");
    return s.substr(first,last-first+1);
}
bool depLess(const DependencyVersion& a,const DependencyVersion& b) {
    if(a.major!=b.major) return a.major<b.major;
    if(a.minor!=b.minor) return a.minor<b.minor;
    return a.patch<b.patch;
}
bool depEqual(const DependencyVersion& a,const DependencyVersion& b) {
    return a.major==b.major&&a.minor==b.minor&&a.patch==b.patch;
}
struct DepAtom { std::string op; DependencyVersion v; };
std::vector<DepAtom> depAtoms(const std::string& raw) {
    std::vector<DepAtom> out;
    std::stringstream ss(depTrim(raw)); std::string part;
    while(std::getline(ss,part,',')) {
        part=depTrim(part); if(part.empty()||part=="*") continue;
        std::string op;
        if(part.rfind(">=",0)==0||part.rfind("<=",0)==0||part.rfind("==",0)==0||part.rfind("!=",0)==0) op=part.substr(0,2);
        else if(part[0]=='>'||part[0]=='<'||part[0]=='='||part[0]=='^'||part[0]=='~') op=part.substr(0,1);
        else op="==";
        auto v=parseDependencyVersion(depTrim(part.substr(op=="=="&&part.rfind("==",0)!=0?0:op.size())));
        if(v) out.push_back({op,*v});
    }
    return out;
}
bool depAtomMatches(const DependencyVersion& v,const DepAtom& a) {
    if(a.op=="^") {
        if(a.v.major>0) return v.major==a.v.major&&!depLess(v,a.v);
        if(a.v.minor>0) return v.major==0&&v.minor==a.v.minor&&!depLess(v,a.v);
        return v.major==0&&v.minor==0&&v.patch==a.v.patch;
    }
    if(a.op=="~") return v.major==a.v.major&&v.minor==a.v.minor&&!depLess(v,a.v);
    if(a.op=="==") return depEqual(v,a.v);
    if(a.op=="!=") return !depEqual(v,a.v);
    if(a.op==">") return depLess(a.v,v);
    if(a.op==">=") return !depLess(v,a.v);
    if(a.op=="<") return depLess(v,a.v);
    if(a.op=="<=") return !depLess(a.v,v);
    return false;
}
std::filesystem::path dependencyStateRoot() { return handlerStateRoot(); }
std::filesystem::path pythonProjectExecutable(const std::filesystem::path& root) {
    for (const auto& name : {std::string(".venv"), std::string("venv")}) {
#ifdef _WIN32
        const auto candidate = root / name / "Scripts" / "python.exe";
#else
        const auto candidate = root / name / "bin" / "python";
#endif
        std::error_code ec;
        if (std::filesystem::is_regular_file(candidate, ec)) return candidate;
    }
    return {};
}

bool validPythonPackageName(const std::string& p) {
    if (p.empty() || p.size() > 128) return false;
    for (std::size_t i = 0; i < p.size(); ++i) {
        const unsigned char ch = static_cast<unsigned char>(p[i]);
        if (std::isalnum(ch) || ch == '-' || ch == '_' || ch == '.') continue;
        return false;
    }
    return true;
}

bool validNodePackageName(const std::string& p) {
    if (p.empty() || p.size() > 214) return false;
    if (p.find(' ') != std::string::npos || p.find('\\') != std::string::npos ||
        p.find(';') != std::string::npos || p.find('|') != std::string::npos)
        return false;
    for (const unsigned char ch : p) {
        if (std::isalnum(ch) || ch == '-' || ch == '_' || ch == '.' ||
            ch == '@' || ch == '/') continue;
        return false;
    }
    return p.front() != '/' && p.back() != '/';
}

std::vector<std::string> registryVersions(const std::string& ecosystem,const std::string& package,
                                           const std::filesystem::path& root) {
    CommandSpec cmd{"dependency-registry-query",ecosystem=="Python"?"python":"npm",{},RiskLevel::Low,45000};
    if (ecosystem == "Python") cmd.executablePath = pythonProjectExecutable(root);
    if(ecosystem=="Python") cmd.arguments={"-m","pip","index","versions",package,"--disable-pip-version-check"};
    else if(ecosystem=="Node.js") { cmd.arguments={"view",package,"versions","--json"}; cmd.workingDirectory=root; }
    else return {};
    const auto r=executeCommand(cmd);
    if(!r.started||r.exitCode!=0) return {};
    std::vector<std::string> out;
    const std::regex re(R"((?:^|[^0-9])([0-9]+\.[0-9]+(?:\.[0-9]+)?)(?:[-+][0-9A-Za-z.-]+)?(?:$|[^0-9]))");
    for(std::sregex_iterator it(r.output.begin(),r.output.end(),re),end;it!=end;++it) {
        const auto v=(*it)[1].str();
        if(std::find(out.begin(),out.end(),v)==out.end()) out.push_back(v);
    }
    return out;
}
std::string installedDependencyVersion(const std::string& ecosystem,const std::string& package,
                                       const std::filesystem::path& root) {
    CommandSpec cmd{"dependency-current-query",ecosystem=="Python"?"python":"npm",{},RiskLevel::Low,30000};
    if (ecosystem == "Python") cmd.executablePath = pythonProjectExecutable(root);
    if(ecosystem=="Python") cmd.arguments={"-m","pip","show",package,"--disable-pip-version-check"};
    else { cmd.arguments={"ls",package,"--depth=0","--json"}; cmd.workingDirectory=root; }
    const auto r=executeCommand(cmd);
    if(!r.started||r.exitCode!=0) return {};
    std::smatch m;
    if(ecosystem=="Python") {
        const auto pos=r.output.find("Version:");
        if(pos!=std::string::npos) {
            const auto begin=pos+8;
            const auto end=r.output.find_first_of("\r\n",begin);
            return depTrim(r.output.substr(begin,end==std::string::npos?r.output.size()-begin:end-begin));
        }
    } else {
        const std::string dependencyKey = "\"" + package + "\"";
        const auto dependencyPos = r.output.find(dependencyKey);
        if (dependencyPos != std::string::npos) {
            const auto versionKey = r.output.find("\"version\"", dependencyPos + dependencyKey.size());
            if (versionKey != std::string::npos) {
                const auto firstQuote = r.output.find('"', r.output.find(':', versionKey) + 1);
                if (firstQuote != std::string::npos) {
                    const auto secondQuote = r.output.find('"', firstQuote + 1);
                    if (secondQuote != std::string::npos)
                        return r.output.substr(firstQuote + 1, secondQuote - firstQuote - 1);
                }
            }
        }
    }
    return {};
}
}

std::optional<DependencyVersion> parseDependencyVersion(const std::string& text) {
    std::smatch m;
    const std::regex re(R"(^\s*[v=]?([0-9]+)(?:\.([0-9]+))?(?:\.([0-9]+))?(?:[-+][0-9A-Za-z.-]+)?\s*$)");
    if(!std::regex_match(text,m,re)) return std::nullopt;
    return DependencyVersion{std::stoi(m[1].str()),m[2].matched?std::stoi(m[2].str()):0,
                             m[3].matched?std::stoi(m[3].str()):0,text};
}
bool satisfiesDependencyConstraint(const DependencyVersion& v,const std::string& constraint) {
    for(const auto& atom:depAtoms(constraint))
        if(!depAtomMatches(v,atom)) return false;
    return true;
}
bool dependencyConstraintsCompatible(const std::vector<std::string>& constraints) {
    if (constraints.empty()) return false;

    std::vector<DependencyVersion> candidates;
    for (const auto& constraint : constraints) {
        for (const auto& atom : depAtoms(constraint)) {
            candidates.push_back(atom.v);
            if (atom.v.patch < 2147483647)
                candidates.push_back({atom.v.major, atom.v.minor, atom.v.patch + 1, {}});
            if (atom.v.patch > 0)
                candidates.push_back({atom.v.major, atom.v.minor, atom.v.patch - 1, {}});
        }
    }

    for (const auto& candidate : candidates) {
        bool ok = true;
        for (const auto& constraint : constraints) {
            if (!satisfiesDependencyConstraint(candidate, constraint)) {
                ok = false;
                break;
            }
        }
        if (ok) return true;
    }
    return false;
}
std::optional<std::string> selectCompatibleDependencyVersion(
    const std::vector<std::string>& constraints,const std::vector<std::string>& availableVersions) {
    std::optional<DependencyVersion> best;
    for(const auto& text:availableVersions) {
        auto v=parseDependencyVersion(text); if(!v) continue;
        bool ok=true;
        for(const auto& c:constraints) ok=ok&&satisfiesDependencyConstraint(*v,c);
        if(ok&&(!best||depLess(*best,*v))) best=*v;
    }
    return best?std::optional<std::string>(best->text):std::nullopt;
}

int upgradeDependency(const std::filesystem::path& projectRoot,const std::string& ecosystem,
                      const std::string& package,const std::string& constraint) {
    if (ecosystem != "Python" && ecosystem != "Node.js") {
        std::cerr<<"Dependency upgrade blocked: unsupported ecosystem.\n"; return 3;
    }
    if ((ecosystem == "Python" && !validPythonPackageName(package)) ||
        (ecosystem == "Node.js" && !validNodePackageName(package))) {
        std::cerr<<"Dependency upgrade blocked: invalid package name.\n"; return 3;
    }
    if (ecosystem == "Python" && pythonProjectExecutable(projectRoot).empty()) {
        std::cerr << "Dependency upgrade blocked: Python project-local .venv or venv is required.\\n"; return 3;
    }
    const auto versions=registryVersions(ecosystem,package,projectRoot);
    const auto selected=selectCompatibleDependencyVersion({constraint},versions);
    if(!selected) { std::cerr<<"No registry version satisfies "<<package<<" "<<constraint<<".\n"; return 4; }
    const auto current=installedDependencyVersion(ecosystem,package,projectRoot);
    if(!current.empty()) {
        const auto cv=parseDependencyVersion(current); const auto sv=parseDependencyVersion(*selected);
        if(cv&&sv&&!depLess(*cv,*sv)) { std::cout<<package<<" is already at a compatible version ("<<current<<").\n"; return 0; }
    }
    std::cout<<"Resolved upgrade: "<<package<<" "<<(current.empty()?"unknown":current)<<" -> "<<*selected<<" ["<<ecosystem<<"]\n"
             <<"Apply this transactional upgrade? [y/N]: ";
    std::string answer; std::getline(std::cin,answer);
    if(answer!="y"&&answer!="Y") { std::cout<<"Dependency upgrade cancelled.\n"; return 2; }

    const auto artifactRoot=dependencyStateRoot()/"transactions"/"artifacts"/"dependency-upgrade";
    std::vector<ArtifactBackup> backups;
    if (ecosystem == "Python") {
        for (const auto& file : {projectRoot/"requirements.txt", projectRoot/"pyproject.toml"}) {
            const auto backup = backupArtifact(file, artifactRoot/"python");
            if (!backup) {
                std::cerr << "Dependency upgrade blocked: transaction artifact backup failed for "
                          << file << ".\n";
                return 1;
            }
            backups.push_back(*backup);
        }
    } else {
        for (const auto& file : {projectRoot/"package.json", projectRoot/"package-lock.json"}) {
            const auto backup = backupArtifact(file, artifactRoot/"node");
            if (!backup) {
                std::cerr << "Dependency upgrade blocked: transaction artifact backup failed for "
                          << file << ".\n";
                return 1;
            }
            backups.push_back(*backup);
        }
    }

    Transaction tx(SafetyMode::Confirm);
    const auto result=tx.runApproved(RiskLevel::High,
        [&] {
            CommandSpec cmd{"dependency-upgrade",ecosystem=="Python"?"python":"npm",{},RiskLevel::High,180000};
            if(ecosystem=="Python") { cmd.arguments={"-m","pip","install",package+"=="+*selected,"--disable-pip-version-check","--only-binary=:all:"}; cmd.executablePath=pythonProjectExecutable(projectRoot); }
            else { cmd.arguments={"install",package+"@"+*selected,"--no-audit","--no-fund","--ignore-scripts"}; cmd.workingDirectory=projectRoot; }
            const auto r=executeCommand(cmd); std::cout<<r.output; return r.started&&r.exitCode==0;
        },
        [&] {
            const auto after=installedDependencyVersion(ecosystem,package,projectRoot);
            const bool passed=after==*selected;
            return VerificationResult{passed,"installed version == "+*selected,passed?"":"installed version was "+after};
        },
        [&] {
            bool restored = true;
            for (const auto& backup : backups) restored = restoreArtifact(backup) && restored;
            if (!restored) return false;

            if (ecosystem == "Node.js") {
                const std::filesystem::path lockfile = projectRoot / "package-lock.json";
                const bool hasLockfile = std::filesystem::is_regular_file(lockfile);
                CommandSpec rollback{"dependency-upgrade-rollback", "npm",
                    hasLockfile
                        ? std::vector<std::string>{"ci", "--ignore-scripts", "--no-audit", "--no-fund"}
                        : std::vector<std::string>{"install", "--ignore-scripts", "--no-audit", "--no-fund"},
                    RiskLevel::High, 180000};
                rollback.workingDirectory = projectRoot;
                const auto r = executeCommand(rollback);
                if (!r.started || r.exitCode != 0) return false;
                return current.empty()
                    ? installedDependencyVersion(ecosystem, package, projectRoot).empty()
                    : installedDependencyVersion(ecosystem, package, projectRoot) == current;
            }

            if (current.empty()) {
                CommandSpec rollback{"dependency-upgrade-rollback", "python",
                    {"-m", "pip", "uninstall", "-y", package, "--disable-pip-version-check"},
                    RiskLevel::High, 120000};
                rollback.executablePath = pythonProjectExecutable(projectRoot);
                const auto r = executeCommand(rollback);
                if (!r.started || r.exitCode != 0) return false;
                return installedDependencyVersion(ecosystem, package, projectRoot).empty();
            }

            CommandSpec rollback{"dependency-upgrade-rollback", "python",
                {"-m", "pip", "install", package + "==" + current,
                 "--disable-pip-version-check", "--only-binary=:all:"},
                RiskLevel::High, 120000};
            rollback.executablePath = pythonProjectExecutable(projectRoot);
            const auto r = executeCommand(rollback);
            if (!r.started || r.exitCode != 0) return false;
            return installedDependencyVersion(ecosystem, package, projectRoot) == current;
        });

    History history(dependencyStateRoot()/"history.log");
    if(!result.committed) {
        history.record("DEPENDENCY_UPGRADE_FAILED",package+" | "+result.details+" | snapshot="+result.snapshotId);
        std::cerr<<"Dependency upgrade did not commit: "<<result.details<<"\n"; return 1;
    }
    history.record("DEPENDENCY_UPGRADE_SUCCESS",package+" | "+*selected+" | snapshot="+result.snapshotId);
    std::cout<<"Dependency upgrade verified and committed.\n";
    return 0;
}

} // namespace handler
