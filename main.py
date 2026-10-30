
from fastapi import FastAPI, UploadFile, File, HTTPException
import pandas as pd
from io import BytesIO

app = FastAPI(
    title="Sales KPI Analysis API",
    description="Upload CSV files to calculate sales KPIs",
    version="1.1.0"
)


@app.get("/")
def home():
    return {
        "message": "Sales Analysis API is running"
    }


@app.post("/analyze")
async def analyze_csv(file: UploadFile = File(...)):

    # 1. Validate file extension
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file"
        )

    try:
        # 2. Read uploaded file
        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded CSV file is empty"
            )

        # 3. Read CSV with UTF-8 BOM support
        df = pd.read_csv(
            BytesIO(content),
            encoding="utf-8-sig"
        )

        # 4. Clean and normalize column names
        df.columns = (
            df.columns
            .astype(str)
            .str.replace("\ufeff", "", regex=False)
            .str.strip()
            .str.lower()
        )

        # Debug information for Render logs
        print("CSV Columns:", df.columns.tolist())

        # 5. Validate required columns
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
                detail={
                    "message": "Missing required CSV columns",
                    "missing_columns": sorted(list(missing)),
                    "received_columns": df.columns.tolist()
                }
            )

        # 6. Count original rows
        original_rows = len(df)

        if original_rows == 0:
            raise HTTPException(
                status_code=400,
                detail="CSV file contains no data rows"
            )

        # 7. Remove exact duplicate rows
        df = df.drop_duplicates()

        duplicates_removed = original_rows - len(df)

        # 8. Handle missing customer names
        missing_customers = int(
            df["customer"].isna().sum()
        )

        df["customer"] = df["customer"].fillna("Unknown")

        # 9. Convert numeric columns
        df["quantity"] = pd.to_numeric(
            df["quantity"],
            errors="coerce"
        )

        df["unit_price"] = pd.to_numeric(
            df["unit_price"],
            errors="coerce"
        )

        # 10. Remove invalid rows
        df = df.dropna(
            subset=[
                "order_id",
                "quantity",
                "unit_price",
                "product"
            ]
        )

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="No valid sales records found in CSV"
            )

        # 11. Calculate sales
        df["sales"] = (
            df["quantity"] * df["unit_price"]
        )

        # 12. Calculate KPIs
        total_sales = float(
            df["sales"].sum()
        )

        total_orders = int(
            df["order_id"].nunique()
        )

        total_customers = int(
            df["customer"].nunique()
        )

        average_order_value = (
            round(total_sales / total_orders, 2)
            if total_orders > 0
            else 0
        )

        # 13. Product-wise sales
        product_sales = (
            df.groupby("product")["sales"]
            .sum()
            .round(2)
            .to_dict()
        )

        # 14. Return JSON response
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

    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=400,
            detail="CSV file has no readable data"
        )

    except pd.errors.ParserError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CSV format: {str(e)}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"CSV processing failed: {str(e)}"
        )
