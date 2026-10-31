from fastapi import FastAPI, UploadFile, File, HTTPException
import pandas as pd
from io import BytesIO
from pathlib import Path

app = FastAPI(
    title="AI Business Data Analysis API",
    description="Professional Excel and CSV Sales Analysis API",
    version="2.0.0"
)


@app.get("/")
def home():
    return {
        "message": "AI Business Data Analysis API is running",
        "version": "2.0.0",
        "supported_files": [".csv", ".xlsx"],
        "endpoint": "/analyze"
    }


@app.post("/analyze")
async def analyze_sales(file: UploadFile = File(...)):

    # STEP 1: Validate file extension
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in [".csv", ".xlsx"]:
        raise HTTPException(
            status_code=400,
            detail="Only CSV and XLSX files are supported."
        )

    # STEP 2: Read uploaded file
    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    try:
        if extension == ".csv":
            df = pd.read_csv(
                BytesIO(contents),
                encoding="utf-8-sig"
            )
        else:
            df = pd.read_excel(
                BytesIO(contents),
                engine="openpyxl"
            )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to read file: {str(e)}"
        )

    # STEP 3: Normalize column names
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    required_columns = [
        "order_id",
        "order_date",
        "customer",
        "product",
        "category",
        "quantity",
        "unit_price",
        "unit_cost",
        "region",
        "payment_status"
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Missing required columns",
                "missing_columns": missing_columns,
                "required_columns": required_columns
            }
        )

    total_rows_received = len(df)

    # STEP 4: Remove exact duplicate rows
    df = df.drop_duplicates().copy()

    duplicates_removed = (
        total_rows_received - len(df)
    )

    # STEP 5: Clean text columns
    text_columns = [
        "order_id",
        "customer",
        "product",
        "category",
        "region",
        "payment_status"
    ]

    for col in text_columns:
        df[col] = (
            df[col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    # STEP 6: Identify missing customers
    missing_customers = (
        df["customer"].eq("").sum()
    )

    df["customer"] = df["customer"].replace(
        "", "Unknown"
    )

    # STEP 7: Convert numeric columns
    numeric_columns = [
        "quantity",
        "unit_price",
        "unit_cost"
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # STEP 8: Validate important fields
    df["order_date"] = pd.to_datetime(
        df["order_date"],
        errors="coerce"
    )

    valid_rows = (
        df["order_id"].ne("")
        & df["product"].ne("")
        & df["category"].ne("")
        & df["region"].ne("")
        & df["payment_status"].ne("")
        & df["quantity"].notna()
        & df["unit_price"].notna()
        & df["unit_cost"].notna()
        & df["order_date"].notna()
        & df["quantity"].gt(0)
        & df["unit_price"].ge(0)
        & df["unit_cost"].ge(0)
    )

    invalid_rows_removed = int((~valid_rows).sum())

    df = df.loc[valid_rows].copy()

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="No valid records found after data cleaning."
        )

    # STEP 9: Normalize payment status
    df["payment_status"] = (
        df["payment_status"].str.lower()
    )

    paid_df = df[
        df["payment_status"] == "paid"
    ].copy()

    pending_df = df[
        df["payment_status"] == "pending"
    ].copy()

    # STEP 10: Calculate Revenue, Cost and Profit
    paid_df["revenue"] = (
        paid_df["quantity"] * paid_df["unit_price"]
    )

    paid_df["cost"] = (
        paid_df["quantity"] * paid_df["unit_cost"]
    )

    paid_df["profit"] = (
        paid_df["revenue"] - paid_df["cost"]
    )

    pending_df["pending_amount"] = (
        pending_df["quantity"] * pending_df["unit_price"]
    )

    total_revenue = float(paid_df["revenue"].sum())

    total_cost = float(paid_df["cost"].sum())

    gross_profit = total_revenue - total_cost

    profit_margin = (
        (gross_profit / total_revenue) * 100
        if total_revenue else 0
    )

    total_orders = int(
        paid_df["order_id"].nunique()
    )

    total_customers = int(
        paid_df.loc[
            paid_df["customer"] != "Unknown",
            "customer"
        ].nunique()
    )

    total_units_sold = int(
        paid_df["quantity"].sum()
    )

    average_order_value = (
        total_revenue / total_orders
        if total_orders else 0
    )

    # STEP 11: Product-wise Analysis
    product_sales = (
        paid_df.groupby("product")["revenue"]
        .sum()
        .round(2)
        .to_dict()
    )

    product_profit = (
        paid_df.groupby("product")["profit"]
        .sum()
        .round(2)
        .to_dict()
    )

    top_product = (
        max(product_sales, key=product_sales.get)
        if product_sales else None
    )

    # STEP 12: Region-wise Analysis
    region_sales = (
        paid_df.groupby("region")["revenue"]
        .sum()
        .round(2)
        .to_dict()
    )

    top_region = (
        max(region_sales, key=region_sales.get)
        if region_sales else None
    )

    # STEP 13: Payment Analysis
    pending_orders = int(
        pending_df["order_id"].nunique()
    )

    pending_amount = float(
        pending_df["pending_amount"].sum()
    )

    # STEP 14: Date Range
    start_date = df["order_date"].min()
    end_date = df["order_date"].max()

    # STEP 15: Return Structured JSON
    return {
        "status": "success",
        "project": "AI Business Data Analysis",

        "file_information": {
            "filename": filename,
            "total_rows_received": total_rows_received,
            "valid_rows": len(df)
        },

        "data_quality": {
            "duplicates_removed": int(duplicates_removed),
            "missing_customers": int(missing_customers),
            "invalid_rows_removed": invalid_rows_removed
        },

        "reporting_period": {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        },

        "sales_kpis": {
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "total_customers": total_customers,
            "total_units_sold": total_units_sold,
            "average_order_value": round(average_order_value, 2)
        },

        "profit_analysis": {
            "total_cost": round(total_cost, 2),
            "gross_profit": round(gross_profit, 2),
            "profit_margin_percent": round(profit_margin, 2)
        },

        "payment_analysis": {
            "pending_orders": pending_orders,
            "pending_amount": round(pending_amount, 2)
        },

        "product_analysis": {
            "product_sales": product_sales,
            "product_profit": product_profit,
            "top_product": top_product
        },

        "region_analysis": {
            "region_sales": region_sales,
            "top_region": top_region
        }
    }