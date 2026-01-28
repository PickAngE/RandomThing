import os
import sys
import sqlite3
import shutil
import tempfile
import time
from typing import List, Tuple, Dict
from dataclasses import dataclass
from enum import Enum

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

class BrowserType(Enum):
    CHROMIUM = "chromium"
    FIREFOX = "firefox"

@dataclass
class BrowserConfig:
    name: str
    type: BrowserType
    paths: List[str]
    history_file: str
    process_names: List[str]

BROWSERS_CONFIG = [
    BrowserConfig("Google Chrome", BrowserType.CHROMIUM, [os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")], "History", ["chrome.exe"]),
    BrowserConfig("Microsoft Edge", BrowserType.CHROMIUM, [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")], "History", ["msedge.exe"]),
    BrowserConfig("Mozilla Firefox", BrowserType.FIREFOX, [os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles")], "places.sqlite", ["firefox.exe"]),
]

class Colors:
    CYAN, GREEN, YELLOW, RED, BOLD, END = '\033[96m', '\033[92m', '\033[93m', '\033[91m', '\033[1m', '\033[0m'
    @staticmethod
    def enable():
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)

def check_running(process_names):
    import subprocess
    try:
        res = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, creationflags=0x08000000)
        return any(p.lower() in res.stdout.lower() for p in process_names)
    except: return False

def force_close(process_names):
    import subprocess
    for p in process_names:
        subprocess.run(['taskkill', '/F', '/IM', p, '/T'], capture_output=True, creationflags=0x08000000)

def find_profiles(config):
    profiles = []
    for base in config.paths:
        if not os.path.exists(base): continue
        if config.type == BrowserType.CHROMIUM:
            if os.path.exists(os.path.join(base, "Default", "History")): profiles.append(os.path.join(base, "Default", "History"))
            for d in os.listdir(base):
                if d.startswith("Profile ") and os.path.exists(os.path.join(base, d, "History")): profiles.append(os.path.join(base, d, "History"))
        else:
            for d in os.listdir(base):
                if os.path.exists(os.path.join(base, d, "places.sqlite")): profiles.append(os.path.join(base, d, "places.sqlite"))
    return profiles

def get_sql_logic(site):
    site = site.lower().strip().replace('https://', '').replace('http://', '').replace('www.', '').rstrip('/')
    pts = [f'%://{site}', f'%://{site}/%', f'%://www.{site}', f'%://www.{site}/%', f'%.{site}', f'%.{site}/%']
    return ' OR '.join(['url LIKE ?' for _ in pts]), pts

def clean_db(path, site, b_type):
    try:
        tmp = os.path.join(tempfile.mkdtemp(), "tmp.db")
        shutil.copy2(path, tmp)
        conn = sqlite3.connect(tmp)
        c = conn.cursor()
        where, params = get_sql_logic(site)
        table = "urls" if b_type == BrowserType.CHROMIUM else "moz_places"
        c.execute(f"SELECT id FROM {table} WHERE {where}", params)
        ids = [r[0] for r in c.fetchall()]
        if not ids: return 0
        if b_type == BrowserType.CHROMIUM:
            for i in ids: c.execute("DELETE FROM visits WHERE url = ?", (i,))
        else:
            for i in ids: c.execute("DELETE FROM moz_historyvisits WHERE place_id = ?", (i,))
        c.execute(f"DELETE FROM {table} WHERE {where}", params)
        conn.commit(); conn.close()
        shutil.copy2(tmp, path)
        return len(ids)
    except: return -1

def main():
    Colors.enable()
    browsers = []
    for b in BROWSERS_CONFIG:
        p = find_profiles(b)
        if p: browsers.append((b, p))
    
    if not browsers:
        print(f"{Colors.RED}[!] Aucun navigateur détecté.{Colors.END}")
        return

    site = input(f"\n{Colors.BOLD}Site à supprimer > {Colors.END}").strip()
    if not site: return

    to_close = []
    for b, _ in browsers:
        if check_running(b.process_names): to_close.extend(b.process_names)
    
    if to_close:
        print(f"{Colors.YELLOW}[!] Fermeture des navigateurs...{Colors.END}")
        force_close(list(set(to_close)))
        time.sleep(1.5)

    print(f"\n{Colors.CYAN}[*] Nettoyage en cours...{Colors.END}")
    for b, profiles in browsers:
        count = 0
        for p in profiles:
            res = clean_db(p, site, b.type)
            if res > 0: count += res
        
        status = f"{Colors.GREEN}{count} entrées" if count > 0 else f"{Colors.YELLOW}Rien"
        if count == -1: status = f"{Colors.RED}Erreur"
        print(f"  > {b.name}: {status}{Colors.END}")

    print(f"\n{Colors.GREEN}[OK] Terminé pour '{site}'.{Colors.END}\n")

if __name__ == "__main__":
    main()