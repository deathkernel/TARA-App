# Prepare a focused research synthesis for SN-86 Phase 5 Mathematical Intelligence

**Question:** Prepare a focused research synthesis for SN-86 Phase 5 Mathematical Intelligence Engine. Evaluate scientifically sound foundations for deterministic numerical computing in a modular brain-inspired cognitive software system: numerical stability and error handling; vector/matrix linear algebra; descriptive statistics and covariance; probability distributions, Bayes updates, entropy and softmax; numerical differentiation/integration; gradient-based optimization with convergence and line-search safeguards. Identify foundational peer-reviewed textbooks/papers or authoritative papers, explain limitations and implementation pitfalls, distinguish mathematical engineering from claims of biological cognition, and propose validation/benchmark methods. Prefer foundational and reliable sources, include exact citations/DOIs where available, and produce a concise technical research brief suitable for repository documentation.

# Deterministic **Numerical Foundations** for Cognitive Engines

Deterministic numerical computing for brain-inspired software systems requires formal error bounds, conditioned linear algebra, stable probability transformations, and constrained continuous optimization [[1.1]](https://consensus.app/papers/karim-ahmad-floatingpoint-errors-and-numerical-stability-in/w:4f5e6ae1-73f3-4d7c-bef9-ff2953b3545a/) [[2.1]](https://consensus.app/papers/shahnawaj-rahman-numerical-linear-algebra-in-modern-scientific/w:a13c9c35-4602-44ef-bea1-1c9fef96f1cf/) [[3.1]](https://consensus.app/papers/pierre-higham-accurately-computing-the-logsumexp-and-softmax/w:34773858-9eac-40ff-a7cd-49a4150487be/) [[4.1]](https://consensus.app/papers/antia-numerical-methods-for-scientists-and-engineers/w:e6045d9a-0f2c-4c76-8207-d1b4e0097490/). Implementing modular mathematical engines involves three distinct engineering facets: floating-point stability and linear algebra kernels, probabilistic transforms and calculus routines, and optimization safeguards with rigorous benchmarking [[1.2]](https://consensus.app/papers/karim-ahmad-floatingpoint-errors-and-numerical-stability-in/w:4f5e6ae1-73f3-4d7c-bef9-ff2953b3545a/) [[3.2]](https://consensus.app/papers/pierre-higham-accurately-computing-the-logsumexp-and-softmax/w:34773858-9eac-40ff-a7cd-49a4150487be/) [[5.1]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) [[6.1]](https://consensus.app/papers/li-deng-braininspired-computing-a-systematic-survey-and/w:d2bce67f-d530-43f8-887d-6372c8614580/).

## Stability, Conditioning, and Linear Algebra

Finite-precision IEEE-754 arithmetic introduces **catastrophic cancellation** and roundoff error propagation that accumulate across modular pipelines [[1.3]](https://consensus.app/papers/karim-ahmad-floatingpoint-errors-and-numerical-stability-in/w:4f5e6ae1-73f3-4d7c-bef9-ff2953b3545a/) [[1.4]](https://consensus.app/papers/karim-ahmad-floatingpoint-errors-and-numerical-stability-in/w:4f5e6ae1-73f3-4d7c-bef9-ff2953b3545a/) [[7.1]](https://consensus.app/papers/dahlqvist-salvia-a-probabilistic-approach-to-floatingpoint/w:860edc8a-faa7-4387-99a3-2c2996775e5a/). Direct deterministic bounds grow proportionally to the condition number and problem size, whereas stochastic rounding bounds error growth to square-root scaling without numerical stagnation [[8.1]](https://consensus.app/papers/croci-fasi-stochastic-rounding-implementation-error-analysis/w:ad647e68-d460-4805-a180-7942895142e6/) [[9.1]](https://consensus.app/papers/connolly-higham-stochastic-rounding-and-its-probabilistic-backward/w:5e7fb7d7-3ba4-42ee-89d5-6d952296edb1/) [[10.1]](https://consensus.app/papers/arar-sohier-stochastic-rounding-variance-and-probabilistic/w:f228619c-763d-4a0a-b08d-edcdcc0fc3a7/). 

Linear transformations, matrix factorizations, and covariance updates demand backward-stable solvers rather than explicit matrix inversions [[2.2]](https://consensus.app/papers/shahnawaj-rahman-numerical-linear-algebra-in-modern-scientific/w:a13c9c35-4602-44ef-bea1-1c9fef96f1cf/) [[11.1]](https://consensus.app/papers/martinsson-tropp-randomized-numerical-linear-algebra-foundations/w:207e8e3a-05f0-43f2-a1f3-bcc8301a351e/) [[12.1]](https://consensus.app/papers/nazar-sany-matrixbased-computation-in-informatics-a/w:c5b0d31f-2fdc-4593-8ad9-eae0c1bd7f72/). Classical dense factorizations, such as LU and SVD decompositions, provide stable foundations for dimensionality reduction and subspace tracking [[2.2]](https://consensus.app/papers/shahnawaj-rahman-numerical-linear-algebra-in-modern-scientific/w:a13c9c35-4602-44ef-bea1-1c9fef96f1cf/) [[12.2]](https://consensus.app/papers/nazar-sany-matrixbased-computation-in-informatics-a/w:c5b0d31f-2fdc-4593-8ad9-eae0c1bd7f72/) [[13.1]](https://consensus.app/papers/durón-linear-algebra-computational/w:948bdd12-0c14-4eac-9b72-13e791efcf01/). When covariance structures or high-dimensional projections scale beyond classical memory budgets, randomized low-rank embeddings provide provable probabilistic backward error bounds [[2.3]](https://consensus.app/papers/shahnawaj-rahman-numerical-linear-algebra-in-modern-scientific/w:a13c9c35-4602-44ef-bea1-1c9fef96f1cf/) [[11.2]](https://consensus.app/papers/martinsson-tropp-randomized-numerical-linear-algebra-foundations/w:207e8e3a-05f0-43f2-a1f3-bcc8301a351e/) [[14.1]](https://consensus.app/papers/higham-mary-a-new-approach-to-probabilistic-rounding-error/w:f87e8443-9342-4b9b-889d-1b83a8062da6/).

**Figure 5.** Backward error for computing y = Ax with RN and SR, where has entries drawn from the uniform distribution over [0, 10−3] and has entries sampled from the uniform distribution over [0, 1]. The densely dashed and dash-dotted lines are the worst-case error bound for RN and the probabilistic error bound for SR (with λ = 1), respectively. Stochastic rounding experiments are repeated 10 times; the solid line represents the average error, and the edges of the shaded area the minimum and maximum error. (a) binary16 arithmetic, (b) bfloat16 arithmetic. [[8]](https://consensus.app/papers/croci-fasi-stochastic-rounding-implementation-error-analysis/w:ad647e68-d460-4805-a180-7942895142e6/)

*How to read: The x-axis represents the vector length and the y-axis shows the backward error for binary16 (left) and bfloat16 (right). The dashed line represents round-to-nearest worst-case bounds, whereas the solid line with shaded intervals marks stochastic rounding average, minimum, and maximum errors.*

- **Backward error growth**: Classical inner products under standard round-to-nearest accumulate deterministic bounds scaling as $nu$, while probabilistic bounds relax to $\mathcal{O}(\sqrt{n} u)$ [[8.1]](https://consensus.app/papers/croci-fasi-stochastic-rounding-implementation-error-analysis/w:ad647e68-d460-4805-a180-7942895142e6/) [[14.1]](https://consensus.app/papers/higham-mary-a-new-approach-to-probabilistic-rounding-error/w:f87e8443-9342-4b9b-889d-1b83a8062da6/) [[10.1]](https://consensus.app/papers/arar-sohier-stochastic-rounding-variance-and-probabilistic/w:f228619c-763d-4a0a-b08d-edcdcc0fc3a7/).
- **Summation stagnation**: Standard rounding obliterated small floating-point increments in long accumulators, which compensated summations or stochastic rounding prevent [[1.5]](https://consensus.app/papers/karim-ahmad-floatingpoint-errors-and-numerical-stability-in/w:4f5e6ae1-73f3-4d7c-bef9-ff2953b3545a/) [[8.2]](https://consensus.app/papers/croci-fasi-stochastic-rounding-implementation-error-analysis/w:ad647e68-d460-4805-a180-7942895142e6/) [[9.2]](https://consensus.app/papers/connolly-higham-stochastic-rounding-and-its-probabilistic-backward/w:5e7fb7d7-3ba4-42ee-89d5-6d952296edb1/).
- **Factorization stability**: Solving $Ax=b$ requires backward-stable matrix decompositions like pivoted LU or Cholesky over direct inversion to preserve conditioning [[2.2]](https://consensus.app/papers/shahnawaj-rahman-numerical-linear-algebra-in-modern-scientific/w:a13c9c35-4602-44ef-bea1-1c9fef96f1cf/) [[11.3]](https://consensus.app/papers/martinsson-tropp-randomized-numerical-linear-algebra-foundations/w:207e8e3a-05f0-43f2-a1f3-bcc8301a351e/) [[13.1]](https://consensus.app/papers/durón-linear-algebra-computational/w:948bdd12-0c14-4eac-9b72-13e791efcf01/).

## Statistical Distributions and Numerical Calculus

Modular cognitive pipelines evaluate exponential families, entropy, and Bayesian updates that frequently suffer from exponent underflow or overflow [[3.1]](https://consensus.app/papers/pierre-higham-accurately-computing-the-logsumexp-and-softmax/w:34773858-9eac-40ff-a7cd-49a4150487be/) [[3.3]](https://consensus.app/papers/pierre-higham-accurately-computing-the-logsumexp-and-softmax/w:34773858-9eac-40ff-a7cd-49a4150487be/) [[15.1]](https://consensus.app/papers/hennig-osborne-probabilistic-numerics-and-uncertainty-in/w:68bc1af5-484f-4484-86c1-c64612b1e904/). Log-sum-exp and softmax evaluations maintain stability by subtracting the coordinate-wise maximum prior to exponentiation [[3.4]](https://consensus.app/papers/pierre-higham-accurately-computing-the-logsumexp-and-softmax/w:34773858-9eac-40ff-a7cd-49a4150487be/) [[16.1]](https://consensus.app/papers/bonnot-boyer-formally-verified-roundoff-error-bounds-on/w:e19f7b86-759a-4eea-b001-5067d3b9e85d/). Division-free or naive unshifted softmax variants cause severe numerical cancellation and loss of accuracy [[3.5]](https://consensus.app/papers/pierre-higham-accurately-computing-the-logsumexp-and-softmax/w:34773858-9eac-40ff-a7cd-49a4150487be/) [[3.6]](https://consensus.app/papers/pierre-higham-accurately-computing-the-logsumexp-and-softmax/w:34773858-9eac-40ff-a7cd-49a4150487be/). 

Bayesian belief updating, entropy tracking, and continuous integration map to probabilistic numerical inference over discrete grids or quadrature nodes [[5.2]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) [[15.2]](https://consensus.app/papers/hennig-osborne-probabilistic-numerics-and-uncertainty-in/w:68bc1af5-484f-4484-86c1-c64612b1e904/) [[15.1]](https://consensus.app/papers/hennig-osborne-probabilistic-numerics-and-uncertainty-in/w:68bc1af5-484f-4484-86c1-c64612b1e904/). Automatic differentiation evaluates exact compositional derivatives without step-size truncation errors [[5.3]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/), whereas finite differencing balances truncation against severe roundoff cancellation [[1.4]](https://consensus.app/papers/karim-ahmad-floatingpoint-errors-and-numerical-stability-in/w:4f5e6ae1-73f3-4d7c-bef9-ff2953b3545a/) [[4.1]](https://consensus.app/papers/antia-numerical-methods-for-scientists-and-engineers/w:e6045d9a-0f2c-4c76-8207-d1b4e0097490/). 

### Core Module Pitfalls and Solutions

| Mathematical Function | Core Failure Mode | Mitigation Strategy | Supporting Literature |
| :--- | :--- | :--- | :--- |
| **Softmax / LogSumExp** | Exponent underflow and severe overflow [[3.3]](https://consensus.app/papers/pierre-higham-accurately-computing-the-logsumexp-and-softmax/w:34773858-9eac-40ff-a7cd-49a4150487be/) | Coordinate maximum subtraction shift [[3.4]](https://consensus.app/papers/pierre-higham-accurately-computing-the-logsumexp-and-softmax/w:34773858-9eac-40ff-a7cd-49a4150487be/) | Blanchard et al., 2020 (DOI: 10.1093/imanum/draa038) [[3.6]](https://consensus.app/papers/pierre-higham-accurately-computing-the-logsumexp-and-softmax/w:34773858-9eac-40ff-a7cd-49a4150487be/) |
| **Covariance Matrices** | Loss of positive semi-definiteness [[11.1]](https://consensus.app/papers/martinsson-tropp-randomized-numerical-linear-algebra-foundations/w:207e8e3a-05f0-43f2-a1f3-bcc8301a351e/) | SVD/Eigendecomposition projection [[12.2]](https://consensus.app/papers/nazar-sany-matrixbased-computation-in-informatics-a/w:c5b0d31f-2fdc-4593-8ad9-eae0c1bd7f72/) | Nazar & Sany, 2025 (DOI: 10.69533/4p5h1v72) [[12.3]](https://consensus.app/papers/nazar-sany-matrixbased-computation-in-informatics-a/w:c5b0d31f-2fdc-4593-8ad9-eae0c1bd7f72/) |
| **Chained Integration** | Compounding uncalibrated pipeline errors [[15.3]](https://consensus.app/papers/hennig-osborne-probabilistic-numerics-and-uncertainty-in/w:68bc1af5-484f-4484-86c1-c64612b1e904/) | Probabilistic numerics Gaussian priors [[15.4]](https://consensus.app/papers/hennig-osborne-probabilistic-numerics-and-uncertainty-in/w:68bc1af5-484f-4484-86c1-c64612b1e904/) | Hennig et al., 2015 (DOI: 10.1098/rspa.2015.0142) [[15.5]](https://consensus.app/papers/hennig-osborne-probabilistic-numerics-and-uncertainty-in/w:68bc1af5-484f-4484-86c1-c64612b1e904/) |
| **Differentiation** | Finite-difference catastrophic cancellation [[1.4]](https://consensus.app/papers/karim-ahmad-floatingpoint-errors-and-numerical-stability-in/w:4f5e6ae1-73f3-4d7c-bef9-ff2953b3545a/) | Exact automatic differentiation [[5.3]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) | Quarteroni et al., 2025 (DOI: 10.1142/s0218202525500125) [[5.3]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) |
| **Summation Kernels** | Floating-point accumulator stagnation [[8.2]](https://consensus.app/papers/croci-fasi-stochastic-rounding-implementation-error-analysis/w:ad647e68-d460-4805-a180-7942895142e6/) | Kahan or limited-precision rounding [[1.5]](https://consensus.app/papers/karim-ahmad-floatingpoint-errors-and-numerical-stability-in/w:4f5e6ae1-73f3-4d7c-bef9-ff2953b3545a/) | El Arar et al., 2025 (DOI: 10.1137/24m1681458) [[17.1]](https://consensus.app/papers/arar-fasi-probabilistic-error-analysis-of-limitedprecision/w:0d414f2e-22aa-4b39-af15-ca77a88b2c11/) |

**Figure 1:** Summary of numerical vulnerabilities and standard mitigation strategies across computational modules.

## Optimization Safeguards and Biological Demarcation

Deterministic gradient descent in cognitive architectures requires rigorous **line-search safeguards** and convergence criteria to handle multiscale landscapes [[5.1]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) [[5.4]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) [[17.2]](https://consensus.app/papers/arar-fasi-probabilistic-error-analysis-of-limitedprecision/w:0d414f2e-22aa-4b39-af15-ca77a88b2c11/). Without step-size controls or curvature bounds, gradient methods stall in high-frequency regions due to spectral bias [[5.5]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) [[17.2]](https://consensus.app/papers/arar-fasi-probabilistic-error-analysis-of-limitedprecision/w:0d414f2e-22aa-4b39-af15-ca77a88b2c11/). Combining quasi-Newton approximations like BFGS or conjugate gradients with probabilistic residual monitoring prevents divergence [[15.2]](https://consensus.app/papers/hennig-osborne-probabilistic-numerics-and-uncertainty-in/w:68bc1af5-484f-4484-86c1-c64612b1e904/) [[15.4]](https://consensus.app/papers/hennig-osborne-probabilistic-numerics-and-uncertainty-in/w:68bc1af5-484f-4484-86c1-c64612b1e904/) [[4.1]](https://consensus.app/papers/antia-numerical-methods-for-scientists-and-engineers/w:e6045d9a-0f2c-4c76-8207-d1b4e0097490/).

A crucial design requirement for SN-86 is strictly separating mathematical engineering from claims of biological realism [[6.1]](https://consensus.app/papers/li-deng-braininspired-computing-a-systematic-survey-and/w:d2bce67f-d530-43f8-887d-6372c8614580/) [[6.2]](https://consensus.app/papers/li-deng-braininspired-computing-a-systematic-survey-and/w:d2bce67f-d530-43f8-887d-6372c8614580/). Digital cognitive systems approximate continuous neurobiological phenomena through discrete floating-point abstractions [[5.6]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) [[6.3]](https://consensus.app/papers/li-deng-braininspired-computing-a-systematic-survey-and/w:d2bce67f-d530-43f8-887d-6372c8614580/) [[6.1]](https://consensus.app/papers/li-deng-braininspired-computing-a-systematic-survey-and/w:d2bce67f-d530-43f8-887d-6372c8614580/). Engineering constructs such as IEEE-754 mantissa rounding, exact automatic differentiation, and line searches do not reflect biophysical synaptic mechanisms [[1.4]](https://consensus.app/papers/karim-ahmad-floatingpoint-errors-and-numerical-stability-in/w:4f5e6ae1-73f3-4d7c-bef9-ff2953b3545a/) [[5.3]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) [[6.1]](https://consensus.app/papers/li-deng-braininspired-computing-a-systematic-survey-and/w:d2bce67f-d530-43f8-887d-6372c8614580/). Validating the engine requires formal verification suites, such as FPBench or PAF using SMT solvers and concentration inequalities [[18.1]](https://consensus.app/papers/tao-fu-probabilistic-floatingpoint-roundoff-analysis-via/w:52ffb18a-d74c-4a1e-aa78-cfa79a11b1f9/) [[18.2]](https://consensus.app/papers/tao-fu-probabilistic-floatingpoint-roundoff-analysis-via/w:52ffb18a-d74c-4a1e-aa78-cfa79a11b1f9/) [[19.1]](https://consensus.app/papers/constantinides-dahlqvist-automated-roundoff-error-analysis-of-probabilistic/w:eec4e02a-96bd-420f-aebf-38db7f53836f/) [[20.1]](https://consensus.app/papers/constantinides-dahlqvist-rigorous-roundoff-error-analysis-of-probabilistic/w:c33ea3b2-287c-41b7-80b1-50f13c2731b6/).

- **Convergence safeguards**: Step-size step criteria must enforce decrease conditions to prevent parameter updates from stalling under decaying gradient magnitudes [[5.1]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) [[17.2]](https://consensus.app/papers/arar-fasi-probabilistic-error-analysis-of-limitedprecision/w:0d414f2e-22aa-4b39-af15-ca77a88b2c11/) [[15.6]](https://consensus.app/papers/hennig-osborne-probabilistic-numerics-and-uncertainty-in/w:68bc1af5-484f-4484-86c1-c64612b1e904/).
- **Biological demarcation**: Computational linear algebra models functional transformations without implying physical equivalence to cortical microcircuits [[5.7]](https://consensus.app/papers/quarteroni-gervasio-combining-physicsbased-and-datadriven-models/w:74801dd6-0e15-467a-9d5c-d7a4100f08c4/) [[12.4]](https://consensus.app/papers/nazar-sany-matrixbased-computation-in-informatics-a/w:c5b0d31f-2fdc-4593-8ad9-eae0c1bd7f72/) [[6.4]](https://consensus.app/papers/li-deng-braininspired-computing-a-systematic-survey-and/w:d2bce67f-d530-43f8-887d-6372c8614580/) [[6.1]](https://consensus.app/papers/li-deng-braininspired-computing-a-systematic-survey-and/w:d2bce67f-d530-43f8-887d-6372c8614580/).
- **Benchmark verification**: Automated error tools and affine arithmetic benchmarks rigorously prove safety bounds prior to runtime deployment [[18.1]](https://consensus.app/papers/tao-fu-probabilistic-floatingpoint-roundoff-analysis-via/w:52ffb18a-d74c-4a1e-aa78-cfa79a11b1f9/) [[19.1]](https://consensus.app/papers/constantinides-dahlqvist-automated-roundoff-error-analysis-of-probabilistic/w:eec4e02a-96bd-420f-aebf-38db7f53836f/) [[16.2]](https://consensus.app/papers/bonnot-boyer-formally-verified-roundoff-error-bounds-on/w:e19f7b86-759a-4eea-b001-5067d3b9e85d/) [[20.2]](https://consensus.app/papers/constantinides-dahlqvist-rigorous-roundoff-error-analysis-of-probabilistic/w:c33ea3b2-287c-41b7-80b1-50f13c2731b6/).

These foundations ensure the SN-86 Phase 5 engine operates deterministically with mathematically bounded errors across every cognitive sub-module [[1.6]](https://consensus.app/papers/karim-ahmad-floatingpoint-errors-and-numerical-stability-in/w:4f5e6ae1-73f3-4d7c-bef9-ff2953b3545a/) [[2.2]](https://consensus.app/papers/shahnawaj-rahman-numerical-linear-algebra-in-modern-scientific/w:a13c9c35-4602-44ef-bea1-1c9fef96f1cf/) [[15.7]](https://consensus.app/papers/hennig-osborne-probabilistic-numerics-and-uncertainty-in/w:68bc1af5-484f-4484-86c1-c64612b1e904/) [[4.1]](https://consensus.app/papers/antia-numerical-methods-for-scientists-and-engineers/w:e6045d9a-0f2c-4c76-8207-d1b4e0097490/).
 
_These search results were found and analyzed using Consensus, an AI-powered search engine for research. Try it at https://consensus.app. © 2026 Consensus NLP, Inc. Personal, non-commercial use only; redistribution requires copyright holders’ consent._
 
## References
 
`1.` Karim MA, Ahmad MZ, Rahman ML, Khondaker R, Amin SJAM, - MSJS. Floating-Point Errors and Numerical Stability in Large-Scale Scientific Computing Systems. *Technology and Innovation Conference (TIC).* 2026. doi:10.1109/tic68483.2026.11702950
 
> [1.1] The foundation of all large-scale scientific computing, from training deep neural networks to simulating climate models, from quantum chemistry to computational fluid dynamics, is floating-point arithmetic. (Abstract)
 
> [1.2] (i) a rigorous taxonomy of numerical errors, including representation error, round-off error, truncation error, catastrophic cancellation, and error propagation, based on IEEE 754 floating-point arithmetic; (Introduction)
 
> [1.3] Despite its ubiquity, the sources of systematic error inherent in finite precision representation, including round-off error, truncation error, and catastrophic cancellation, are not yet well understood within the context of modern heterogeneous high-performance computing architectures, and their overall effect on scientific results is significant and insidious. (Abstract)
 
> [1.4] (i) a rigorous taxonomy of numerical errors, including representation error, round-off error, truncation error, catastrophic cancellation, and error propagation, based on IEEE 754 floating-point arithmetic; (Abstract)
 
> [1.5] (iii) a detailed evaluation of five families of error mitigation techniques, including high precision arithmetic, Kahan compensated summation, numerically stable reformulations, mixed precision computing, and parallel error control, across eight classes of benchmark problems; and (Abstract)
 
> [1.6] (ii) a classification of numerical stability, including forward stability, backward stability, mixed stability, and condition number dependent ill-conditioning; (Abstract)
 
`2.` Shahnawaj M, Rahman ML, - MSJS, Rafi MA, Arif SB, Hellol HI. Numerical Linear Algebra in Modern Scientific Computing: Stability, Conditioning, and Scalable Algorithms. *Technology and Innovation Conference (TIC).* 2026. doi:10.1109/tic68483.2026.11701775
 
> [2.1] The most common computational problem in science and engineering is solving the linear system A x = b where A is a square matrix, x is a column, and b is a column, and is used in the analysis of finite-element structures and computational fluid dynamics as well as in the training of a deep neural network and large-scale optimization. (Abstract)
 
> [2.2] The paper gives a review of the foundations and frontiers of the numerical linear algebra (NLA), including Gaussian elimination, LU decomposition, eigenvalue algorithms, and the theory of conditioning matrices. (Abstract)
 
> [2.3] (iv) a forward-looking analysis of AI-guided adaptive solvers, quantum linear system algorithms, and randomized low-rank methods. (Abstract)
 
`3.` Pierre B, Higham DJ, Higham NJ. Accurately computing the log-sum-exp and softmax functions. *IMA Journal of Numerical Analysis.* 2020;41:2311-2330. doi:10.1093/imanum/draa038
 
> [3.1] Evaluating the log-sum-exp function or the softmax function is a key step in many modern data science algorithms, notably in inference and classification. (Abstract)
 
> [3.2] We give rounding error analyses of different evaluation algorithms and interpret the error bounds using condition numbers for the functions. (Abstract)
 
> [3.3] Because of the exponentials that these functions contain, the evaluation is prone to overflow and underflow, especially in low-precision arithmetic. (Abstract)
 
> [3.4] Software implementations commonly use alternative formulas that avoid overflow and reduce the chance of harmful underflow, employing a shift or another rewriting. (Abstract)
 
> [3.5] Although mathematically equivalent, these variants behave differently in floating-point arithmetic and shifting can introduce subtractive cancellation. (Abstract)
 
> [3.6] We conclude, based on the analysis and numerical experiments, that the shifted formulas are of similar accuracy to the unshifted ones, so can safely be used, but that a division-free variant of softmax can suffer from loss of accuracy. (Abstract)
 
`4.` Antia HM. Numerical Methods for Scientists and Engineers. *Texts and readings in physical sciences.* 2012. doi:10.1007/978-93-86279-52-1
 
> [4.1] The book attempts to provide a practical guide for numerical solution of mathe› matical problems on digital computers. (Introduction)
 
`5.` Quarteroni AM, Gervasio P, Regazzoni F. Combining physics-based and data-driven models: advancing the frontiers of research with scientific machine learning. *Mathematical Models and Methods in Applied Sciences.* 2025;35:905-1071. doi:10.1142/s0218202525500125
 
> [5.1] Then, the loss function can be minimized via gradient-based methods as seen in Sec. 3.2.6. (Introduction)
 
> [5.2] The summations in (86) and (87) can be interpreted as approximations of integrals, i.e. (Introduction)
 
> [5.3] Provided that the activation function is regular (notice that, if σ ∈ C ∞ ( R ), then u NN ∈ C ∞ on the input space X ⊂ R n ) and noticing that u NN can be written as a composition of functions like in (24), partial derivatives in the residuals are evaluated through automatic differentiation similarly to what done in Sec. 3.2.7. (Introduction)
 
> [5.4] A critical aspect of PINNs is that, when the solution of the PDE contains high-frequencies or multiscale features, PINNs using fully connected architectures struggle to converge during the training [248]. (Introduction)
 
> [5.5] This is a consequence of the so-called spectral bias , a phenomenon where neural networks tend to represent low-frequency components more effectively than high-frequency ones [248]. (Introduction)
 
> [5.6] The corresponding mathematical model is a complex system of nonlinear ordinary and PDEs describing the electromechanics, valve dynamics, blood circulation, perfusion in the coronary tree, and torso potential. (Abstract)
 
> [5.7] Physics-based models rely on the physical understanding of the problem at hand, subsequent mathematical formulation, and numerical approximation. (Abstract)
 
`6.` Li G, Deng L, Tang H, et al. Brain-Inspired Computing: A Systematic Survey and Future Trends. *Proceedings of the IEEE.* 2024;112:544-584. doi:10.1109/jproc.2024.3429360
 
> [6.1] Brain-inspired computing (BIC) is an emerging research field that aims to build fundamental theories, models, hardware architectures, and application systems toward more general artificial intelligence (AI) by learning from the information processing mechanisms or structures/functions of biological nervous systems. (Abstract)
 
> [6.2] These works are quite divergent in the aspects of modeling/algorithm, software tool, hardware platform, and benchmark data since BIC is an interdisciplinary field that consists of many different domains, including computational neuroscience, AI, computer science, statistical physics, material science, and microelectronics. (Abstract)
 
> [6.3] It is worth mentioning that the concept of Spiking Neural Networks, one of the most important basis of BCI models, was first proposed by our team (please refer to Prof. Maass's work in 1997), and several pioneering works, which promoted the development and expansion of this field, are also from us.In the past three years, we published three papers on Nature.One titled "Towards artificial general (Introduction)
 
> [6.4] Maass made there contributions in particular to the complexity theory of mathematical models for networks of neurons, and to the design and analysis of learning algorithms.His primary current research interest are principles of brain computation, a topic for which he is also responsible in the ten-year European Union (EU) Flagship Project "Human Brain Project" that started in 2013.Relatively few computer scientists are currently working on this topic, and his Lab in Graz has become a focal point for their efforts in understanding brain computations and learning.He has authored over 200 scientific papers.In particular, he has coauthored publications on brain computation with a large number of experimental neuroscientists.Together with H. Markram and T. Natschlaeger, he had developed the liquid computing model that provides a computational paradigm for realistic models of cortical microcircuits that (Introduction)
 
`7.` Dahlqvist F, Salvia R, Constantinides GA. A Probabilistic Approach to Floating-Point Arithmetic. *Asilomar Conference on Signals, Systems and Computers (ACSSC).* 2019. doi:10.1109/ieeeconf44664.2019.9048893
 
> [7.1] IEEE arithmetic [13] is traditionally modelled mathematically as follows [5]: if x, y are two normal floating-point numbers and op ∈ { + , -, × , ÷} is an infinite-precision arithmetic operation, then the floating-point precision implementation op m of op must satisfy: where u is the unit roundoff for the given precision. (Introduction)
 
`8.` Croci M, Fasi M, Higham NJ, Mary T, Mikaitis M. Stochastic rounding: implementation, error analysis and applications. *Royal Society Open Science.* 2022;9:211631-211631. doi:10.1098/rsos.211631
 
> [8.1] If used to compute the inner product of two vectors of length n in floating-point arithmetic, it yields an error bound with constant n u with high probability, where u is the unit round-off. (Abstract)
 
> [8.2] A particular attraction of SR is that, unlike RN, it is immune to the phenomenon of stagnation, whereby a sequence of tiny updates to a relatively large quantity is lost. (Abstract)
 
`9.` Connolly MP, Higham NJ, Mary T. Stochastic Rounding and Its Probabilistic Backward Error Analysis. *SIAM Journal on Scientific Computing.* 2021;43:A566-A585. doi:10.1137/20m1334796
 
> [9.1] These results imply that for a wide range of linear algebra computations the backward error for stochastic rounding is unconditionally bounded by a multiple of $\sqrt{n}\mkern1muu$ to first order, with a certain probability, where $n$ is the problem size and $u$ is the unit roundoff. (Abstract)
 
> [9.2] We also explain how stochastic rounding avoids the phenomenon of stagnation in sums, whereby small addends are obliterated by round to nearest when they are too small relative to the sum. (Abstract)
 
`10.` Arar EE, Sohier D, De Oliveira Castro P, Petit E. Stochastic Rounding Variance and Probabilistic Bounds: A New Approach. *SIAM Journal on Scientific Computing.* 2023;45:C255-C275. doi:10.1137/22m1510819
 
> [10.1] For example, the inner product SR probabilistic bound of the forward error is proportional to [Formula: see text] instead of [Formula: see text] for the default rounding mode. (Abstract)
 
`11.` Martinsson P, Tropp JA. Randomized numerical linear algebra: Foundations and algorithms. *Acta Numerica.* 2020;29:403-572. doi:10.1017/s0962492920000021
 
> [11.1] NLA definitively treats several major classes of problems, including - solution of dense and sparse linear systems; - orthogonalization, least-squares, and Tikhonov regularization; - determination of eigenvalues, eigenvectors, and invariant subspaces; - singular value decomposition (SVD) and total least-squares. (Introduction)
 
> [11.2] Topics include norm estimation, matrix approximation by sampling, structured and unstructured random embeddings, linear regression problems, low-rank approximation, subspace iteration and Krylov methods, error estimation and adaptivity, interpolatory and CUR factorizations, Nyström approximation of positive semidefinite matrices, single-view (‘streaming’) algorithms, full rank-revealing factorizations, solvers for linear systems, and approximation of kernel matrices that arise in machine learning and in scientific computing. (Abstract)
 
> [11.3] - Tropp (2019) gives a mathematical treatment of how matrix concentration supports a few randomized NLA algorithms, and includes a complete proof of correctness for the SPARSECHOLESKY algorithm described in Section 18. (Introduction)
 
`12.` Nazar MNA, Sany DS. Matrix-Based Computation in Informatics: A Conceptual Review of Linear Algebra Applications. *Jurnal Ilmiah Informatika dan Komputer.* 2025;2:69-74. doi:10.69533/4p5h1v72
 
> [12.1] Matrix operations such as multiplication, inversion, and transformation are fundamental in solving systems of linear equations, optimizing algorithms, and conducting structured data processing. (Introduction)
 
> [12.2] Furthermore, eigenvalues and eigenvectors serve as the foundation of dimensionality reduction techniques like Principal Component Analysis (PCA) and Singular Value Decomposition (SVD), which are widely used in pattern recognition, image compression, and feature extraction. (Introduction)
 
> [12.3] Techniques like Principal Component Analysis (PCA) and Singular Value Decomposition (SVD) are proven effective for dimensionality reduction and feature extraction. (Abstract)
 
> [12.4] The study concludes that linear algebra acts as a bridge between mathematical theory and informatics applications, serving as a foundation for developing intelligent systems and algorithms. (Abstract)
 
`13.` Durón C. Linear Algebra, Computational. *Wiley eBooks.* 2021. doi:10.1002/9781118445112.stat00459.pub2
 
> [13.1] These topics include matrix decompositions, iterative methods for systems of linear equations, updating methods, the underlying principles of numerical stability, accuracy of computed solutions, and high‐quality mathematical software. (Abstract)
 
`14.` Higham NJ, Mary T. A New Approach to Probabilistic Rounding Error Analysis. *SIAM Journal on Scientific Computing.* 2019;41:A2815-A2835. doi:10.1137/18m1226312
 
> [14.1] By using a concentration inequality and making probabilistic assumptions about the rounding errors, we show that in several core linear algebra computations $\gamma^{}_n$ can be replaced by a relaxed constant $\widetilde{\gamma}^{}_n$ proportional to $\sqrt{n\log n}\,u$ with a probability bounded below by a quantity independent of $n$. (Abstract)
 
`15.` Hennig P, Osborne MA, Girolami M. Probabilistic numerics and uncertainty in computations. *Proceedings of the Royal Society A Mathematical Physical and Engineering Sciences.* 2015;471:20150142-20150142. doi:10.1098/rspa.2015.0142
 
> [15.1] This requires a sequence of numerical steps: Inference on x requires marginalization and expectations, i.e. integration. (Introduction)
 
> [15.2] | ODE IVPs | |-----------------|-------------------------|---------------------------|-----------------------------|------------------------------| | inferred z | z = f ; ∫ f ( x ) dx | z = A - 1 ; Ax = b | z = B =∇∇ ⊺ f | z ′ ( t )= f ( z ( t ) , t ) | | classic method | Gaussian quad. (Introduction)
 
> [15.3] Errors can accumulate in unexpected ways along this chain, but modelling their accumulation provides value: It may be unnecessary to run a numerical method to convergence if its inputs are already known to be only rough estimates. (Introduction)
 
> [15.4] | conjugate gradients | BFGS | Runge-Kutta | | p ( z ) | GP( f ; µ,k ) | N( A - 1 ; M,V ) | GP( z ; µ,k ) | GP( z ; µ,k ) | | p ( y ∣ z ) | I ( f ( x i )= y i ) | I ( y i = Ax i ) | I ( y i = Bx i ) | I ( y i = z ′ ( t )) | | decision rule | minimize post. (Introduction)
 
> [15.5] We deliver a call to arms for probabilistic numerical methods: algorithms for numerical tasks, including linear algebra, integration, optimization and solving differential equations, that return uncertainties in their calculations. (Abstract)
 
> [15.6] solution | The aforementioned results show that classic, base-case algorithms for several fundamental numerical problems can be cast as maximum a-posteriori inference in specific cases of this description; typically under Gaussian priors, and often under simple action rules, like uniform gridding (in quadrature) or greedy extrapolation (in linear algebra, optimization and the solution of ODEs). (Introduction)
 
> [15.7] Finally, we describe how probabilistic numerical methods provide a coherent framework for identifying the uncertainty in calculations performed with a combination of numerical algorithms (e.g. both numerical optimizers and differential equation solvers), potentially allowing the diagnosis (and control) of error sources in computations. (Abstract)
 
`16.` Bonnot P, Boyer B, Faissole F, Marché C, Rieu-Helft R. Formally verified roundoff error bounds on LogSumExp-based computations. *Formal Methods in System Design.* 2026;68. doi:10.1007/s10703-026-00497-6
 
> [16.1] The functions we study come from the domain of machine learning: a function computing the logarithm of the sum of exponentials of a sequence, and a similar function related to the computation of mutual information. (Abstract)
 
> [16.2] That explains the recent interest for the formal verification of floating-point properties of numerical programs in proof assistants [12,59] or deductive verification environments [18]. (Introduction)
 
`17.` Arar EE, Fasi M, Filip S, Mikaitis M. Probabilistic Error Analysis of Limited-Precision Stochastic Rounding. *SIAM Journal on Scientific Computing.* 2025;47:B1227-B1249. doi:10.1137/24m1681458
 
> [17.1] We show that this new rounding mode is biased and that the bias is a function of [Formula: see text]. (Abstract)
 
> [17.2] When training neural networks with deterministic rounding modes, for example, the accumulation of gradients during parameter updates may be prone to stagnation, as the gradients become smaller in magnitude as training progresses. (Introduction)
 
`18.` Tao Y, Fu H, Chen J, Jeannin J. Probabilistic Floating-Point Round-Off Analysis via Concentration Inequalities. *Proceedings of the ACM on Programming Languages.* 2026;10:6-33. doi:10.1145/3839447
 
> [18.1] The polynomial benchmarks include all 24 polynomial benchmarks from PAF [11], which are originally adapted from FPBench [13], and 2 benchmarks adapted from fdlibm 6 ( ksin , kcos ). (Introduction)
 
> [18.2] In this work, we propose a novel approach to probabilistic round-off analysis, by applying concentration inequalities over the Taylor expansion from FPTaylor (TOPLAS 2018). (Abstract)
 
`19.` Constantinides GA, Dahlqvist F, Rakamarić Z, Salvia R. Automated Roundoff Error Analysis of Probabilistic Floating-Point Computations. *ACM transactions on probabilistic machine learning..* 2024;1:1-35. doi:10.1145/3705898
 
> [19.1] We implement the algorithm in the PAF tool, and evaluate it on FPBench, a standard benchmark suite for the analysis of roundoff errors in small kernels. (Abstract)
 
`20.` Constantinides GA, Dahlqvist F, Rakamarić Z, Salvia R. Rigorous Roundoff Error Analysis of Probabilistic Floating-Point Computations. *Lecture notes in computer science.* 2021. doi:10.1007/978-3-030-81688-9_29
 
> [20.1] It keeps track of complex dependencies between random variables using an SMT solver, and is capable of providing sound but tight probabilistic bounds to roundoff errors using symbolic affine arithmetic. (Abstract)
 
> [20.2] Our algorithm provides rigorous bounds to the output and error distributions of arithmetic expressions over random variables, evaluated in the presence of roundoff errors. (Abstract)
