from src.db import SessionLocal
from src.db.models import PurchaseOrder

db = SessionLocal()
count = db.query(PurchaseOrder).count()
print(f'既存発注件数: {count}')

if count > 0:
    print('\n最初の5件:')
    for po in db.query(PurchaseOrder).limit(5).all():
        print(f'  ID={po.id}, 発注番号={po.order_number}, 仕入先={po.supplier}')

db.close()
