# Paper reading template

Paper:
Advanced Traffic Demand Generation in SUMO:
ML-based Prediction of Flow Rate based on Real-world Measured Datasets

## Problem

Why is realistic traffic demand difficult to create in SUMO?

## Dataset

What was measured?
What is one row?
What is the time interval?
Which cities were used for training and validation?

## Model

Which regression models were compared?
What were the input features?
What exactly was the target variable?

## SUMO pipeline

How was the road network created?
How were candidate routes generated?
How was RouteSampler used?
How were predicted counts converted into simulated vehicles?

## Evaluation

What was compared?
Which plots and metrics were reported?
Where did mismatches come from?

## Limitation

What could be improved with XGBoost, LSTM, multi-horizon forecasting,
multiple cities, or better route calibration?

## My reproduction

What part is exact?
What part is simplified?
What data is synthetic?
What will be replaced by real UTD19 data?
