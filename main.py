
from fastapi import FastAPI, UploadFile, File, HTTPException
import pandas as pd
from io import BytesIO

app = FastAPI(title="Sales KPI Analysis API")


@app.get("/")
def home():
    return {"message": "Sales Analysis API is running"}


@app.post("/analyze")
async def analyze_csv(file: UploadFile = File(...)):

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file"
        )

    try:
        content = await file.read()
        df = pd.read_csv(BytesIO(content))

        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()

        required = {
            "order_id",
            "order_date",
            "customer",
            "product",
            "quantity",
            "unit_price"
        }

        missing = required - set(df.columns)

        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing columns: {list(missing)}"
            )

        original_rows = len(df)

        # Remove exact duplicate rows
        df = df.drop_duplicates()

        duplicates_removed = original_rows - len(df)

        # Handle missing customer
        missing_customers = int(df["customer"].isna().sum())
        df["customer"] = df["customer"].fillna("Unknown")

        # Convert numeric columns
        df["quantity"] = pd.to_numeric(
            df["quantity"], errors="coerce"
        )
        df["unit_price"] = pd.to_numeric(
            df["unit_price"], errors="coerce"
        )

        df = df.dropna(
            subset=["order_id", "quantity", "unit_price", "product"]
        )

        # Calculate sales
        df["sales"] = df["quantity"] * df["unit_price"]

        total_sales = float(df["sales"].sum())
        total_orders = int(df["order_id"].nunique())
        total_customers = int(df["customer"].nunique())

        average_order_value = (
            round(total_sales / total_orders, 2)
            if total_orders else 0
        )

        # Product-wise sales
        product_sales = (
            df.groupby("product")["sales"]
            .sum()
            .to_dict()
        )

        return {
            "total_sales": total_sales,
            "total_orders": total_orders,
            "total_customers": total_customers,
            "average_order_value": average_order_value,
            "duplicates_removed": duplicates_removed,
            "missing_customers": missing_customers,
            "product_sales": product_sales
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"CSV processing failed: {str(e)}"
        )
