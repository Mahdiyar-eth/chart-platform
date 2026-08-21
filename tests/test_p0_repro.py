#!/usr/bin/env python3
"""P0 reproduction: anonymous buy -> verify -> /chart page rendered state.
Does the paid buyer see the paid/generating report, or fall back to free summary?"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app as main_app
from app.db import engine
from app.models import Order, Report
import importlib

# fake OK gateway
import tests.conftest as cf
class OkZP:
    def verify(self, *a, **k): return {"ref_id":"200000000099","card_pan":"621986****0000"}
    def request(self, *a, **k): return "Sfake", "https://sandbox.zarinpal.com/pg/StartPay/Sfake"

def mk_chart(c):
    d = c.post("/api/charts", data={"calendar":"jalali","year":"1373","month":"6","day":"1",
        "hour":"6","minute":"10","city_fa":"تهران","lat":"35.6889","lon":"51.3897"}).json()
    return d["chart_id"], d["access_token"]

def main():
    import app.main as m
    m.ZarinpalClient = OkZP
    import app.payment.zarinpal as zp
    zp.ZarinpalClient = OkZP
    c = TestClient(main_app)
    cid, tok = mk_chart(c)
    c.cookies.update({"chart_access": json.dumps({cid: tok})})
    print("chart", cid, "token", tok[:8])
    # create order for a report plan
    r = c.post("/api/orders", data={"plan_key":"gold","chart_id":cid})
    print("create_order", r.status_code, r.text[:200])
    oid = r.json()["order_id"]
    # find authority from DB
    with Session(engine) as s:
        o = s.get(Order, oid)
        auth = o.authority
        print("order", o.id, "plan", o.plan_key, "auth", auth[:12], "status", o.status)
    # verify (fake OK)
    v = c.get(f"/api/payments/verify?Authority={auth}&Status=OK", follow_redirects=False)
    print("verify", v.status_code, "Location:", v.headers.get("location"))
    with Session(engine) as s:
        o = s.get(Order, oid)
        print("after verify order.status", o.status, "report_id", o.report_id)
        if o.report_id:
            rep = s.get(Report, o.report_id)
            print("report", rep.id, "status", rep.status, "chart_id", rep.chart_id)
        reports = s.exec(select(Report).where(Report.chart_id==cid)).all()
        print("reports for chart", len(reports))
    # GET payment result
    pr = c.get(f"/payment/result?order_id={oid}")
    print("payment_result", pr.status_code, "paid?", "پرداخت با موفقیت" in pr.text)
    # GET /chart and inspect report section
    ch = c.get(f"/chart/{cid}")
    print("chart_page", ch.status_code, "has_free_section?", "گزارش کامل" in ch.text, "has_generating?", "در حال تولید" in ch.text)
    # poll the report status API exactly as the page JS does
    st = c.get(f"/api/charts/{cid}/report?t={tok}")
    print("report_status_api", st.status_code, st.text[:300])

if __name__=="__main__":
    main()
