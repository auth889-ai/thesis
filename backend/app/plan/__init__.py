"""The person's day, kept true as the world changes.

    day            the timeline: events, tasks due, reminders, and a departure plan for every event and saved commute with a place
    monitor        every few minutes, recompute each upcoming departure; when it moves, tell the person why
    notifications  what the monitor found, unread until seen; delivered by SNS where configured
    outcomes       what actually happened (departed, arrived) and the per-person calibration it implies
    router         GET /api/plan/day, GET/POST /api/notifications, POST /api/outcomes
"""
