import requests

# Yeh woh URL hai jo Apps Script "Deploy > New deployment" ke baad mila tha
# Isko yahan seedha mat likho -- GitHub Secrets se aayega (agla step mein dikhayenge)
import os
APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")


def export_to_google_sheet(outputs: dict):
    """Har section (Gem_Setup_Intraday, Gem_Setup_HigherTF, etc.) ko
    ek alag tab/sheet mein bhej deta hai Apps Script ke through."""
    if not APPS_SCRIPT_URL:
        print("APPS_SCRIPT_URL set nahi hai -- Sheet export skip ho raha hai.")
        return

    for section, df in outputs.items():
        if df.empty:
            rows = [["No rows"]]
        else:
            safe_df = df.fillna("").astype(object)
            rows = [safe_df.columns.tolist()] + safe_df.values.tolist()

        payload = {"sheetName": section[:99], "rows": rows}
        try:
            resp = requests.post(APPS_SCRIPT_URL, json=payload, timeout=30)
            if resp.status_code == 200:
                print(f"Sheet updated: {section} ({len(df)} rows)")
            else:
                print(f"Sheet update failed for {section}: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"Sheet export error for {section}: {e}")


# main() ke andar, export_excel(outputs) ke baad yeh line add kar do:
#   export_to_google_sheet(outputs)
