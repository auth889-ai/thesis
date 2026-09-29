"""The person's calendar, without an OAuth connector: events imported from any iCalendar (.ics) file or
subscription URL (Google, Outlook, Apple and university calendars all export one), plus events the
assistant creates. Events with a location get a departure plan on the day view and are watched for changes.

    ics       a small RFC 5545 reader: VEVENT with DTSTART/DTEND (UTC, local, or date-only), SUMMARY, LOCATION, UID
    store     the events table (same SQLite file as the assistant's world)
    tools     calendar.upcoming, calendar.create_event, calendar.import_url
    router    POST /api/calendar/import (file or URL), GET /api/calendar/events
"""
