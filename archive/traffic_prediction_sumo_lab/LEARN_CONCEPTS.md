# Learn the experiment, not just the commands

## The paper idea in one sentence

Historical traffic measurements are used by a machine-learning model to
predict traffic flow; those predicted counts are converted into SUMO
traffic demand so that a realistic simulation can be generated and
validated.

## Five questions

### 1. What is the original data?

Rows of traffic measurements over time.

Example:

| hour | flow |
|---:|---:|
| 07 | 80 |
| 08 | 145 |
| 09 | 125 |

### 2. What is the model input?

- hour of day
- weekday/weekend
- previous flow values: lag 1, lag 2, lag 3, lag 24

### 3. What is the model output?

Predicted vehicles per hour.

### 4. What does SUMO receive?

A road network plus hourly `<flow>` definitions.

Example:

```xml
<flow begin="28800" end="32400" number="145" route="main"/>
```

Meaning:

Between 08:00 and 09:00 simulation time, SUMO should insert 145 vehicles.

### 5. What does SUMO output?

The realized simulation:

- entered vehicles
- speed
- density
- waiting time
- trip information

## Real dry run

Suppose:

- actual flow at 08:00 = 150
- ML predicted flow = 142

The route generator writes:

```xml
<flow begin="28800" end="32400" number="142" route="main"/>
```

SUMO attempts to insert 142 individual vehicles.

Possible SUMO result:

- entered = 142
- mean speed = 13.1 m/s
- density = 2.4 veh/km

Then there are two different errors:

1. Prediction error: `|150 - 142| = 8`
2. Simulation mismatch: `|142 - 142| = 0`

That distinction is central to the paper's pipeline.
