"""Training on an AWS GPU, launched and collected from the terminal or the app, one module per concern:

    settings    bucket, region, AMI, the pinned harness commits, result paths
    scripts     the user-data scripts the instance runs (benchmarks, city dataset, federated, OpenCity)
    ec2         the aws CLI, the running instances of a job, launching one instance across a ladder of types and zones
    benchmark   the benchmark job: plan, launch, status, collect, terminate
    report      the benchmark table against the published numbers
    city        a city-dataset job: the app's own dataset and configs trained on the GPU, polled, collected as cards
    cli         the command line

`app.forecasting.training.aws_train` remains the import surface and the module to run.
"""
