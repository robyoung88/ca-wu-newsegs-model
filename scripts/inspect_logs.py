# import subprocess
# from datetime import datetime
# import re
# import sys
# from typing import List, Tuple, Optional, Dict

# def fetch_docker_logs(tail_n: int = 1000) -> List[str]:
#     """
#     Fetches the last N log entries from docker compose using --tail
#     to obtain the current log snapshot without hanging on follow mode (-f).
#     """
#     try:
#         cmd = ["docker", "compose", "logs", "--tail", str(tail_n)]
#         result = subprocess.run(
#             cmd,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.STDOUT,
#             text=True,
#             check=True,
#             encoding="utf-8"
#         )
#         return result.stdout.splitlines()
#     except subprocess.CalledProcessError as e:
#         print(f"Error executing docker compose logs: {e}", file=sys.stderr)
#         return []

# def find_active_connections_at(
#     log_entries: List[str], 
#     target_datetime_str: str
# ) -> List[Tuple[str, datetime, Optional[datetime]]]:
#     """
#     Inspects log entries, pairs connection checkouts and returns, and returns 
#     connections open at the specified target datetime (inclusive).
#     """
#     target_dt = datetime.strptime(target_datetime_str, "%Y-%m-%d %H:%M:%S,%f")
    
#     # Regex to handle Docker Compose service prefix (e.g. 'zmq-dispatcher-1  | ') and extract timestamps
#     ts_pattern = re.compile(r"(?:^[^|]+\|\s*)?\[([^\]]+)\]")
#     # Regex to capture SQLite connection memory address objects
#     conn_pattern = re.compile(r"(<sqlite3\.Connection object at 0x[0-9a-fA-F]+>)")
    
#     # Track connection states: conn_addr -> {"checkout": dt, "return": dt or None}
#     connection_sessions: Dict[str, Dict[str, Optional[datetime]]] = {}
#     lines_with_time = 0
#     for line in log_entries:
#         ts_match = ts_pattern.search(line)
#         if not ts_match:
#             continue
            
#         try:
#             log_time = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S,%f")
#         except ValueError:
#             continue
#         lines_with_time += 1
            
#         conn_match = conn_pattern.search(line)
#         if not conn_match:
#             continue
            
#         conn_addr = conn_match.group(1)
        
#         # Match SQLAlchemy pool checkout and return events
#         if any(keyword in line for keyword in ["checked out", "Checkout", "checked out from pool"]):
#             connection_sessions[conn_addr] = {
#                 "checkout": log_time,
#                 "return": None
#             }
#             print(line)
#         elif any(keyword in line for keyword in ["returned", "Checkin", "returned to pool"]):
#             if conn_addr in connection_sessions:
#                 connection_sessions[conn_addr]["return"] = log_time
#             print(line)

#     print (f'Found {lines_with_time} lines with a matching time')
#     print (f'Found {len(connection_sessions)} sessions')   
#     # Filter connections active at target_dt (inclusive of exact matches)
#     active_connections = []
#     for conn_addr, session in connection_sessions.items():
#         checkout = session["checkout"]
#         return_time = session["return"]
        
#         if return_time is None:
#             # If the log window started after checkout and hasn't returned yet
#             if checkout <= target_dt:
#                 active_connections.append((conn_addr, checkout, None))
#         else:
#             # Inclusive check between checkout and return
#             if checkout <= target_dt <= return_time:
#                 active_connections.append((conn_addr, checkout, return_time))
                
#     return active_connections

# if __name__ == "__main__":
#     import argparse
#     parser = argparse.ArgumentParser(description="Inspect pooled connection states from docker compose logs.")
#     parser.add_argument("--tail", type=int, default=1000, help="Number of trailing log entries to fetch (default: 1000)")
#     parser.add_argument("--time", type=str, required=True, help="Target datetime string, e.g., '2026-10-15 10:11:30,500'")
    
#     args = parser.parse_args()
    
#     print(f"Fetching last {args.tail} log entries via docker compose...")
#     logs = fetch_docker_logs(tail_n=args.tail)
    
#     if logs:
#         print(f"Analyzing logs for active connections at: {args.time}\n")
#         active = find_active_connections_at(logs, args.time)
        
#         if active:
#             print(f"Found {len(active)} active connection(s):")
#             for addr, checkout, ret in active:
#                 ret_str = ret.strftime("%Y-%m-%d %H:%M:%S,%f") if ret else "Still Open / Not Returned in Window"
#                 print(f" - Connection: {addr}")
#                 print(f"   Checked out: {checkout.strftime('%Y-%m-%d %H:%M:%S,%f')}")
#                 print(f"   Returned:    {ret_str}")
#                 print("-" * 50)
#         else:
#             print("No active connections found matching the target timestamp within the inspected log window.")

import subprocess
from datetime import datetime
import re
import sys
import json
from typing import List, Dict, Any, Optional

def fetch_docker_logs(tail_n: int = 1000) -> List[str]:
    """
    Fetches the last N log entries from docker compose using --tail
    to obtain the current log snapshot without hanging on follow mode (-f).
    """
    try:
        cmd = ["docker", "compose", "logs", "--tail", str(tail_n)]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
            encoding="utf-8"
        )
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"Error executing docker compose logs: {e}", file=sys.stderr)
        return []

def find_active_connections_at(
    log_entries: List[str], 
    target_datetime_str: str
) -> List[Dict[str, Any]]:
    """
    Parses logs, groups events by connection address, sorts them, pairs checkouts 
    to the next return while validating state rules, calculates durations, and 
    returns sessions active at the target datetime.
    """
    target_dt = datetime.strptime(target_datetime_str, "%Y-%m-%d %H:%M:%S,%f")
    
    # Regex to strip Docker Compose service prefixes and extract timestamps
    log_json_pattern = re.compile(r"(?:^[^|]+\|\s*)(\{.*\})")
    ts_pattern = re.compile(r"(?:^[^|]+\|\s*)?\[([^\]]+)\]")
    conn_pattern = re.compile(r"(<sqlite3\.Connection object at 0x[0-9a-fA-F]+>)")
    
    # Group raw events by connection address
    raw_events: Dict[str, List[Dict[str, Any]]] = {}
    for raw_line in log_entries:
        log_json_match = log_json_pattern.search(raw_line)
        if not log_json_match:
            #print(f'Line does not match pattern: {raw_line}')
            line = raw_line
        else:
            try:
                line_dict = json.loads(log_json_match.group(1))
            except Exception as e:
                print(e)
                print(raw_line)
                continue
            try:
                line = line_dict['message']
            except KeyError:
                print(f'Line has no message: {raw_line}')
                continue

        ts_match = ts_pattern.search(line)
        if not ts_match:
            continue
            
        try:
            log_time = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S,%f")
        except ValueError:
            continue

        if log_time == target_dt:
            print(f'MATCH TIME: {line}')
            
        conn_match = conn_pattern.search(line)
        if not conn_match:
            continue
            
        conn_addr = conn_match.group(1)
        
        event_type = None
        if any(kw in line for kw in ["checked out", "Checkout", "checked out from pool"]):
            event_type = "checkout"
        elif any(kw in line for kw in ["returned", "Checkin", "returned to pool"]):
            event_type = "return"
            
        if event_type:
            if conn_addr not in raw_events:
                raw_events[conn_addr] = []
            raw_events[conn_addr].append({"type": event_type, "time": log_time})
            
    connection_sessions: List[Dict[str, Any]] = []
    
    # Process each connection's lifecycle events
    for conn_addr, events in raw_events.items():
        # Sort events chronologically (stable sort)
        # Do not prefer checkouts, prefer to keep order
        events.sort(key=lambda x: x["time"])
        
        current_checkout = None
        start_of_file = True
        
        for event in events:
            ev_type = event["type"]
            ev_time = event["time"]
            
            if ev_type == "checkout":
                if current_checkout is not None and not start_of_file:
                    raise ValueError(
                        f"Validation Error: Connection {conn_addr} was checked out at {ev_time} "
                        f"before being returned from its previous checkout at {current_checkout}!"
                    )
                current_checkout = ev_time
                start_of_file = False
                
            elif ev_type == "return":
                if current_checkout is None and not start_of_file:
                    raise ValueError(
                        f"Validation Error: Connection {conn_addr} was returned at {ev_time} "
                        f"without a preceding checkout!"
                    )
                if current_checkout is None:
                    current_checkout = events[0]['time']
                
                duration = (ev_time - current_checkout).total_seconds()
                connection_sessions.append({
                    "address": conn_addr,
                    "checkout": current_checkout,
                    "return": ev_time,
                    "duration": duration
                })
                current_checkout = None
                
        # Handle unclosed checkouts at the tail end of the log window
        if current_checkout is not None:
            connection_sessions.append({
                "address": conn_addr,
                "checkout": current_checkout,
                "return": None,
                "duration": None
            })

    durations = [float(x['duration']) for x in connection_sessions if x['duration'] is not None]
    print(f'Found {len(connection_sessions)} connection sessions over {len(raw_events)} connection addresses.')

    print(f'Searching for connections at {target_dt} - Sessions range from {connection_sessions[0]['checkout']} to {connection_sessions[-1]['return']}')
    print(f'{len(durations)} durations are known, ranging from {min(durations)} to {max(durations)}')

    dx = sorted(connection_sessions, key = lambda x: x['duration'])
    print(dx[-1])
    
    # Filter sessions active at the target datetime (inclusive)
    active_connections = []
    for session in connection_sessions:
        checkout = session["checkout"]
        return_time = session["return"]
        
        if return_time is None:
            if checkout <= target_dt:
                active_connections.append(session)
        else:
            if checkout <= target_dt <= return_time:
                active_connections.append(session)
                
    return active_connections

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Inspect pooled connection states from docker compose logs.")
    parser.add_argument("--tail", type=int, default=1000, help="Number of trailing log entries to fetch (default: 1000)")
    parser.add_argument("--time", type=str, required=True, help="Target datetime string, e.g., '2026-10-15 10:11:30,500'")
    
    args = parser.parse_args()
    
    print(f"Fetching last {args.tail} log entries via docker compose...")
    logs = fetch_docker_logs(tail_n=args.tail)
    
    if logs:
        print(f"Analyzing logs for active connections at: {args.time}\n")
        try:
            active = find_active_connections_at(logs, args.time)
            if active:
                print(f"Found {len(active)} active connection session(s):")
                for session in active:
                    ret_str = session["return"].strftime("%Y-%m-%d %H:%M:%S,%f") if session["return"] else "Still Open / Unreturned"
                    dur_str = f"{session['duration']:.3f}s" if session['duration'] is not None else "N/A"
                    print(f" - Address:  {session['address']}")
                    print(f"   Checkout: {session['checkout'].strftime('%Y-%m-%d %H:%M:%S,%f')}")
                    print(f"   Return:   {ret_str}")
                    print(f"   Duration: {dur_str}")
                    print("-" * 50)
            else:
                print("No active connections found matching the target timestamp.")
        except ValueError as e:
            print(f"Log Integrity Error: {e}", file=sys.stderr)
