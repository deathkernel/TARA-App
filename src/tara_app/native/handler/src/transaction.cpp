#include "handler/transaction.h"

#include "handler/environment_state.h"
#include "handler/state_paths.h"
#include "handler/recovery_journal.h"
#include "handler/transaction_lock.h"
#include <cstdlib>

#include <filesystem>
#include <exception>

namespace handler {
namespace {

bool invokeRollbackSafely(const Transaction::Rollback& rollback) noexcept {
    if (!rollback) return false;
    try {
        return rollback();
    } catch (...) {
        return false;
    }
}

void recordRollbackOutcome(const RecoveryJournal& journal,
                           const std::string& transactionId,
                           bool rollbackOk,
                           const std::string& successDetails,
                           const std::string& failureDetails) {
    if (rollbackOk) {
        journal.record(transactionId, "ROLLBACK", successDetails);
    } else {
        journal.record(transactionId, "RECOVERY_REQUIRED", failureDetails);
    }
}

} // namespace

Transaction::Transaction(SafetyMode mode) : mode_(mode) {}

TransactionResult Transaction::run(RiskLevel risk, const Action& action,
                                   const Verify& verify, const Rollback& rollback) {
    return runInternal(false, risk, action, verify, rollback);
}

TransactionResult Transaction::runInternal(bool approved, RiskLevel risk,
                                           const Action& action,
                                           const Verify& verify,
                                           const Rollback& rollback) {
    const auto decision = approved ? PolicyDecision{true, false, "explicitly pre-confirmed"} : evaluatePolicy(mode_, risk);
    if (!decision.allowed)
        return {false, false, false, {}, decision.reason};

    if (!action || !verify)
        return {false, false, false, {}, "invalid transaction callbacks"};

    const auto root = handlerTransactionRoot();
    TransactionLock transactionLock(root / "transaction.lock");
    if (!transactionLock.acquire())
        return {false, false, false, {}, "transaction blocked: another Handler transaction is already active"};

    RecoveryJournal journal(root / "recovery.log");
    const auto transactionId = RecoveryJournal::newTransactionId();
    if (!journal.record(transactionId, "START", "transaction started"))
        return {false, false, false, {}, "transaction aborted: recovery journal unavailable"};

    SnapshotStore snapshots(root / "snapshots");
    const auto snapshot = snapshots.create(captureEnvironmentState());

    if (snapshot) {
        if (!journal.record(transactionId, "SNAPSHOT", snapshot->id))
            return {false, false, true, snapshot->id, "transaction aborted: recovery journal could not record snapshot"};
    } else {
        if (!journal.record(transactionId, "SNAPSHOT_FAILED", "environment snapshot could not be created"))
            return {false, false, false, {}, "transaction aborted: recovery journal unavailable"};
        if (risk != RiskLevel::Low) {
            journal.record(transactionId, "ABORT", "transaction refused because a recovery snapshot was unavailable");
            return {false, false, false, {}, "transaction aborted: recovery snapshot unavailable"};
        }
    }

    if (!journal.record(transactionId, "ACTION_BEGIN", "transaction action started"))
        return {false, false, snapshot.has_value(), snapshot ? snapshot->id : std::string{}, "transaction aborted: recovery journal unavailable before action"};

    bool actionOk = false;
    try {
        actionOk = action();
    } catch (...) {
        const bool rollbackOk = invokeRollbackSafely(rollback);
        recordRollbackOutcome(journal, transactionId, rollbackOk,
                              "action threw an exception; rollback verified by callback",
                              "action threw an exception; recovery is required because rollback failed or was unavailable");
        return {false, rollbackOk, snapshot.has_value(),
                snapshot ? snapshot->id : std::string{}, "action threw an exception; rollback invoked"};
    }
    if (!actionOk) {
        const bool rollbackOk = invokeRollbackSafely(rollback);
        recordRollbackOutcome(journal, transactionId, rollbackOk,
                              "action failed; rollback verified by callback",
                              "action failed; recovery is required because rollback failed or was unavailable");
        return {false, rollbackOk, snapshot.has_value(),
                snapshot ? snapshot->id : std::string{}, "action failed; rollback invoked"};
    }

    if (!journal.record(transactionId, "VERIFY_BEGIN", "transaction verification started")) {
        const bool rollbackOk = invokeRollbackSafely(rollback);
        recordRollbackOutcome(journal, transactionId, rollbackOk,
                              "journal failure; rollback verified by callback",
                              "journal failure; recovery is required because rollback failed or was unavailable");
        return {false, rollbackOk, snapshot.has_value(), snapshot ? snapshot->id : std::string{}, "verification aborted: recovery journal unavailable"};
    }

    VerificationResult verification{};
    try {
        verification = verify();
    } catch (...) {
        const bool rollbackOk = invokeRollbackSafely(rollback);
        recordRollbackOutcome(journal, transactionId, rollbackOk,
                              "verification threw an exception; rollback verified by callback",
                              "verification threw an exception; recovery is required because rollback failed or was unavailable");
        return {false, rollbackOk, snapshot.has_value(),
                snapshot ? snapshot->id : std::string{},
                "verification threw an exception; rollback invoked"};
    }
    if (!verification.passed) {
        const bool rollbackOk = invokeRollbackSafely(rollback);
        recordRollbackOutcome(journal, transactionId, rollbackOk,
                              "verification failed; rollback verified by callback",
                              "verification failed; recovery is required because rollback failed or was unavailable");
        return {false, rollbackOk, snapshot.has_value(),
                snapshot ? snapshot->id : std::string{},
                "verification failed; rollback invoked"};
    }

    const bool commitRecorded = journal.record(transactionId, "COMMIT", "transaction verified");
    return {true, false, snapshot.has_value(),
            snapshot ? snapshot->id : std::string{},
            commitRecorded ? "action verified and committed"
                           : "action verified and committed; recovery journal persistence failed"};
}

TransactionResult Transaction::runApproved(RiskLevel risk, const Action& action,
                                           const Verify& verify, const Rollback& rollback) {
    return runInternal(true, risk, action, verify, rollback);
}

} // namespace handler
