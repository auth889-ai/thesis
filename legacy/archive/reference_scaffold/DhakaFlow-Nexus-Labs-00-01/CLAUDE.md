# Claude research rules for DhakaFlow Nexus

You are the implementation/reproduction partner, not the scientific authority.

## Hard rules

- Work on **one lab at a time**.
- Inspect paper, official repo/scenario, dataset, and git state before changing code.
- Do not invent missing paper details.
- Mark every material choice: PUBLISHED / INFERRED / ASSUMED / MODIFIED_BY_US.
- Do not claim a command ran unless it actually ran.
- Do not claim a metric/plot exists unless it was generated and inspected.
- Do not put multi-GB datasets on the local PC or in Git.
- Use Colab/Drive for Lab 00 full UTD19 processing.
- Use deterministic seeds. Statistical re-sampling is allowed only where the paper requires it; record the seed.
- Do not substitute a new/current Google traffic query for the paper's historical 2019 speed calibration and call it reproduction.
- Preserve upstream official code/scenarios and wrap them rather than rewriting them unnecessarily.

## Lab completion report

Always end with:

- LAB STATUS: PASS / PARTIAL / FAIL
- Exact commands/cells executed
- Inputs and dataset versions
- Outputs and paths
- Paper result vs our result
- Tests
- Assumptions/deviations
- Unresolved issues
- Next recommended action

Then stop. Do not begin the next lab automatically.
