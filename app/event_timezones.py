"""Explicit event timezones with DST gap/fold validation."""
import re
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo,available_timezones

def parse_wall(text):
    for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d %I:%M:%S %p','%Y-%m-%d %H:%M','%Y-%m-%dT%H:%M:%S'):
        try:return datetime.strptime(text.strip().upper(),fmt)
        except ValueError:pass
    raise ValueError('Enter a valid date and time, for example 2026-11-10 13:18:00 or 2026-11-10 01:18:00 PM.')
def zone(value):
    if value=='UTC':return timezone.utc
    m=re.fullmatch(r'UTC([+-])(\d{2}):(\d{2})',value)
    if m:
        minutes=int(m[2])*60+int(m[3])
        if int(m[3])>59 or minutes>14*60:raise ValueError('UTC offset must be between -14:00 and +14:00.')
        return timezone(timedelta(minutes=minutes if m[1]=='+' else -minutes))
    try:return ZoneInfo(value)
    except (KeyError,ValueError):raise ValueError('Choose an IANA zone such as America/New_York, UTC, or a fixed offset such as UTC-05:00.') from None

def resolve_wall(text,zone_name,fold=None):
    wall=parse_wall(text);tz=zone(zone_name);candidates={}
    for f in (0,1):
        dt=wall.replace(tzinfo=tz,fold=f)
        if dt.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)==wall:candidates[dt.utcoffset()]=dt
    if not candidates:raise ValueError('This local time does not exist in the selected zone because clocks jump forward. Choose a real time.')
    if len(candidates)>1:
        if fold not in (0,1):raise ValueError('This local time occurs twice when clocks move back. Select first or second occurrence.')
        return wall.replace(tzinfo=tz,fold=fold)
    return next(iter(candidates.values()))
def fixed_zone(dt):
    seconds=int(dt.utcoffset().total_seconds());sign='+' if seconds>=0 else '-';minutes=abs(seconds)//60
    return f'UTC{sign}{minutes//60:02d}:{minutes%60:02d}'


def detect_local_zone(system_id=None,local_now=None):
    """Detect a real zone where possible; disclose a fixed-offset fallback."""
    from PySide6.QtCore import QTimeZone
    candidate=system_id if system_id is not None else bytes(QTimeZone.systemTimeZoneId()).decode()
    for name in (candidate,bytes(QTimeZone.windowsIdToDefaultIanaId(candidate.encode())).decode()):
        if not name:continue
        try:zone(name);return name,'Detected from this computer'
        except ValueError:pass
    name=fixed_zone(local_now or datetime.now().astimezone())
    return name,'Regional zone unavailable; current fixed offset only. Override with an IANA zone for historical daylight-saving rules.'
