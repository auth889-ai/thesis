# Method Specification

## Research questions

**RQ1.** Can the DhakaFlow code reliably run and observe SUMO using TraCI?

**RQ2.** Under identical seeded demand, do Fixed-Time, queue-actuated and movement Max-Pressure controllers produce measurably different traffic outcomes?

**RQ3.** Can an official real-world Bologna/Acosta scenario be executed unchanged using a pinned official upstream repository?

## Unit-validation controller definitions

### Fixed-Time
Use the static TLS program embedded in the generated network. External code observes only; it does not change the phase plan.

### Queue-actuated
At a green decision point:
1. enforce `min_green`;
2. compare queued vehicles on currently served vs competing approaches;
3. if served demand remains sufficiently high and `max_green` is not reached, extend current green;
4. otherwise terminate green by setting remaining duration to zero, allowing SUMO to move through the declared yellow transition.

### Movement Max-Pressure
For each candidate green stage, identify controlled movements served by green and calculate:

`P(stage) = sum(q_in - q_out)`

where `q_in` and `q_out` are current halting counts on the movement's incoming and outgoing lanes. After `min_green`, retain/extend the current stage if it has the best pressure; otherwise request transition to the next green through the declared yellow phase. The lab's unit network has exactly two green stages, so this transition rule is well-defined and safe.

## Safety model

The declared phase order is:

1. N/S green, E/W red
2. N/S yellow, E/W red
3. N/S red, E/W green
4. N/S red, E/W yellow

The controllers do **not** directly write arbitrary `setRedYellowGreenState` strings. They only alter phase duration, so declared yellow transitions are preserved.

## Fair comparison

For each seed, all three controllers use the exact same generated route file, same network, same vehicle parameters, same simulation horizon, same warm-up handling, and same metric implementation.
