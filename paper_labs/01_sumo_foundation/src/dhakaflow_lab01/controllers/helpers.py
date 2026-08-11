def controlled_links_by_signal(traci, tls_id):
    """Return list indexed by signal index; each item is a list of (in_lane,out_lane,via_lane)."""
    return traci.trafficlight.getControlledLinks(tls_id)

def green_signal_indices(state: str):
    return [i for i, c in enumerate(state) if c in ("G", "g")]

def phase_queue_score(traci, tls_id: str, state: str):
    links = controlled_links_by_signal(traci, tls_id)
    incoming = set()
    for idx in green_signal_indices(state):
        if idx >= len(links):
            continue
        for link in links[idx] or ():
            if link and link[0]:
                incoming.add(link[0])
    return sum(traci.lane.getLastStepHaltingNumber(l) for l in incoming), incoming

def phase_pressure_score(traci, tls_id: str, state: str):
    links = controlled_links_by_signal(traci, tls_id)
    score = 0.0
    movements = []
    for idx in green_signal_indices(state):
        if idx >= len(links):
            continue
        for link in links[idx] or ():
            if not link or len(link) < 2:
                continue
            in_lane, out_lane = link[0], link[1]
            q_in = traci.lane.getLastStepHaltingNumber(in_lane)
            q_out = traci.lane.getLastStepHaltingNumber(out_lane)
            p = float(q_in - q_out)
            score += p
            movements.append((in_lane, out_lane, q_in, q_out, p))
    return score, movements

def tls_logic(traci, tls_id):
    logics = traci.trafficlight.getAllProgramLogics(tls_id)
    if not logics:
        raise RuntimeError(f"No program logic for TLS {tls_id}")
    current_program = traci.trafficlight.getProgram(tls_id)
    for logic in logics:
        if logic.programID == current_program:
            return logic
    return logics[0]

def green_phase_indices(traci, tls_id):
    logic = tls_logic(traci, tls_id)
    return [i for i,p in enumerate(logic.phases) if ("G" in p.state or "g" in p.state) and "y" not in p.state]

def next_green_phase(traci, tls_id, current_idx):
    logic = tls_logic(traci, tls_id)
    greens = green_phase_indices(traci, tls_id)
    if not greens:
        raise RuntimeError("No green phases found")
    for offset in range(1, len(logic.phases)+1):
        i=(current_idx+offset)%len(logic.phases)
        if i in greens:
            return i
    return current_idx
