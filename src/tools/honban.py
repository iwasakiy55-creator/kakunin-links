"""開発版（template.html）を、本番（template.prod.html）に出す。
使い方: py -X utf8 src/tools/honban.py → py -X utf8 src/build.py → git に上げる
データ（data の JSON）は、開発版と本番で同じものを使う（毎日19時の見回りで本番にも出る）"""
import shutil
from pathlib import Path
R = Path(__file__).resolve().parents[1]
shutil.copyfile(R / "template.html", R / "template.prod.html")
print("本番の型を、開発版と同じにしました")
