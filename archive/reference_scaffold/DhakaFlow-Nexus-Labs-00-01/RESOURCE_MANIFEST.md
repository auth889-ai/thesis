# DhakaFlow Nexus — Verified Primary Resource Manifest

This package intentionally uses primary/official sources. It does **not** claim any paper is a universal "world best"; instead it selects the canonical, dataset-defining or software-reference work for each lab.

## Lab 00 — Traffic science / UTD19 / MFD

### Primary paper
- Loder, A., Ambühl, L., Menendez, M., Axhausen, K. W. (2019), **Understanding traffic capacity of urban networks**, Scientific Reports 9, 16283.
- Article: https://www.nature.com/articles/s41598-019-51539-5
- PDF: https://www.nature.com/articles/s41598-019-51539-5.pdf
- DOI: https://doi.org/10.1038/s41598-019-51539-5

### Dataset
- UTD19 official portal: https://utd19.ethz.ch/
- ETH research collection record: https://www.research-collection.ethz.ch/entities/researchdata/bfb14ee7-82c8-4357-a293-3bf18d8f93f9
- Author dataset vignette: https://github.com/ambuehll/UTD19

### Method companions used only to reconstruct published methodology
- Ambühl et al., re-sampling methodology (ETH record): https://www.research-collection.ethz.ch/entities/publication/597b01e7-acac-4f38-8626-6503613f8996
- Functional MFD form metadata: https://www.research-collection.ethz.ch/entities/publication/ccf75694-c2cd-4075-9471-3d06add78f4e

### Scientific classification
Independent paper-faithful reconstruction. The author UTD19 repository is a dataset vignette/supporting repository, not a verified complete official analysis implementation.

## Lab 01 — SUMO foundation / TraCI / traffic-control baselines

### Primary SUMO reference publication
- Alvarez Lopez et al. (2018), **Microscopic Traffic Simulation using SUMO**, ITSC 2018.
- SUMO publication page: https://sumo.dlr.de/docs/Publications.html
- DLR open-access record: https://elib.dlr.de/127994/
- DOI: https://doi.org/10.1109/ITSC.2018.8569938

### Official SUMO software/documentation
- SUMO documentation: https://sumo.dlr.de/docs/index.html
- GitHub: https://github.com/eclipse-sumo/sumo
- TraCI traffic-light tutorial: https://sumo.dlr.de/docs/Tutorials/TraCI4Traffic_Lights.html
- Traffic-light docs: https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html

### Real-world official scenario
- SUMO scenarios documentation: https://sumo.dlr.de/docs/Data/Scenarios.html
- Maintained scenarios repository: https://github.com/DLR-TS/sumo-scenarios
- Bologna/Acosta: https://github.com/DLR-TS/sumo-scenarios/tree/main/bologna/acosta

### Unit-validation scenario
The package also includes a deterministic four-arm intersection solely for unit validation of TraCI/controller logic. It is **not** presented as real-world evidence and is separate from the official Bologna run.

## Storage rule
- Local PC/Git: code, notebooks, configs, tests, small reports/figures only.
- Google Drive: full UTD19, large outputs, caches, future checkpoints.
- Google Colab: full-data/heavy compute.
- Secrets: Colab Secrets or local ignored `.env`; never committed.
