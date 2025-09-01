
import pandas as pd
import streamlit as st

RECOGNIZED_STATUS = "fulfilled"
PAID_STATUS = "paid"

def parse_orders(uploaded_file):
    df = pd.read_csv(uploaded_file)
    df["Paid at"] = pd.to_datetime(df["Paid at"], errors="coerce")
    df["Fulfilled at"] = pd.to_datetime(df["Fulfilled at"], errors="coerce")
    df["Paid Month"] = df["Paid at"].dt.to_period("M")
    df["Fulfilled Month"] = df["Fulfilled at"].dt.to_period("M")

    for col in ["Lineitem quantity", "Lineitem price", "Discount Amount", "Shipping", "Taxes"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["Gross Revenue"] = df["Lineitem quantity"] * df["Lineitem price"]
    return df

def recognized_revenue(df):
    fulfilled = df[df["Fulfillment Status"].str.lower() == RECOGNIZED_STATUS].copy()
    fulfilled["Recognized Discounts"] = fulfilled["Discount Amount"]
    fulfilled["Recognized Shipping"] = fulfilled["Shipping"]
    fulfilled["Recognized Taxes"] = fulfilled["Taxes"]
    fulfilled["Net Recognized Revenue"] = (
        fulfilled["Gross Revenue"] + fulfilled["Recognized Shipping"] - fulfilled["Recognized Discounts"]
    )
    return fulfilled.groupby("Fulfilled Month").agg({
        "Gross Revenue": "sum",
        "Recognized Discounts": "sum",
        "Recognized Shipping": "sum",
        "Recognized Taxes": "sum",
        "Net Recognized Revenue": "sum"
    }).reset_index().rename(columns={"Fulfilled Month": "Month"})

def deferred_revenue(df):
    deferred = df[
        (df["Financial Status"].str.lower() == PAID_STATUS) &
        ((df["Fulfilled at"].isna()) | (df["Paid Month"] != df["Fulfilled Month"]))
    ].copy()
    deferred["Deferred Discount"] = deferred["Discount Amount"]
    deferred["Deferred Shipping"] = deferred["Shipping"]
    deferred["Deferred Taxes"] = deferred["Taxes"]
    deferred["Net Deferred Revenue"] = (
        deferred["Gross Revenue"] + deferred["Deferred Shipping"] - deferred["Deferred Discount"]
    )
    return deferred.groupby("Paid Month").agg({
        "Gross Revenue": "sum",
        "Deferred Discount": "sum",
        "Deferred Shipping": "sum",
        "Deferred Taxes": "sum",
        "Net Deferred Revenue": "sum"
    }).reset_index().rename(columns={"Paid Month": "Month"})

def merchant_cashflow(uploaded_file):
    df = pd.read_csv(uploaded_file)
    df["Transaction Date"] = pd.to_datetime(df["Transaction Date"], errors="coerce")
    df["Month"] = df["Transaction Date"].dt.to_period("M")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df["Fee"] = pd.to_numeric(df["Fee"], errors="coerce")
    df["Net"] = pd.to_numeric(df["Net"], errors="coerce")
    charges = df[df["Type"].str.lower() == "charge"]
    return charges.groupby("Month").agg({
        "Amount": "sum",
        "Fee": "sum",
        "Net": "sum"
    }).reset_index().rename(columns={
        "Amount": "Gross Cash from Customers",
        "Fee": "Merchant Fees",
        "Net": "Net Cash Received"
    })

def summarize(orders_file, transactions_file):
    orders_df = parse_orders(orders_file)
    recognized = recognized_revenue(orders_df)
    deferred = deferred_revenue(orders_df)
    merchant_flow = merchant_cashflow(transactions_file)
    summary = pd.merge(recognized, deferred, on="Month", how="outer")
    summary = pd.merge(summary, merchant_flow, on="Month", how="outer")
    return summary.fillna(0)

# === Streamlit Web App ===
st.set_page_config(page_title="Shopify Revenue Reconciliation Tool")
st.title("📊 Shopify Revenue Reconciliation Tool")

orders_file = st.file_uploader("Upload Shopify Orders CSV", type=["csv"], key="orders")
transactions_file = st.file_uploader("Upload Shopify Payment Transactions CSV", type=["csv"], key="transactions")

if orders_file and transactions_file:
    df_summary = summarize(orders_file, transactions_file)
    st.success("Reconciliation complete.")
    st.dataframe(df_summary)

    csv_export = df_summary.to_csv(index=False).encode("utf-8")
    st.download_button("Download Summary as CSV", csv_export, "monthly_reconciliation.csv", "text/csv")
else:
    st.info("Please upload both the Orders and Payment Transactions CSV files.")
