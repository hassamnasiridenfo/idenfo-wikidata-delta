import sys
import pandas as pd
from image_handler import delete_inactive_images

# Usage: python delete_s3_images.py "<delta_file.xlsx>" <scraper_tag>
delta_file  = sys.argv[1]
scraper_tag = sys.argv[2]

df = pd.read_excel(delta_file)

# is file ke columns DB-style hain -> delete_inactive_images ke expected naam mein rename
df = df.rename(columns={'status': 'Status', 'customer_id': 'ID', 'img_tag': 'Image Tag'})

n0 = int((df['Status'].astype(str).str.strip().isin(['0', '0.0'])).sum())
print(f"File          : {delta_file}")
print(f"Total records : {len(df)}")
print(f"Status=0      : {n0}  (jinke paas Image Tag hai unki images delete hongi)")

delete_inactive_images(df, scraper_tag)
print(f"DONE — log: images-Logs/{scraper_tag}-<date>.log")
