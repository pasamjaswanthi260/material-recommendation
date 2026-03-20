from flask import Flask, render_template, request, jsonify, send_file
import psycopg2
import os
from dotenv import load_dotenv
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table

load_dotenv()
app = Flask(__name__)

# STORE LAST RECOMMENDATIONS
last_results = pd.DataFrame()

# -----------------------------
# DATABASE CONNECTION
# -----------------------------
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

# -----------------------------
# HOME PAGE
# -----------------------------
@app.route('/')
def home():
    return render_template("index.html")

# -----------------------------
# DASHBOARD
# -----------------------------
@app.route('/dashboard')
def dashboard():
    conn = get_connection()
    df = pd.read_sql('SELECT * FROM material', conn)
    conn.close()

    # Detect material name
    def get_material(row):
        for col in df.columns:
            if col.startswith("material_type_") and row[col] == True:
                return col.replace("material_type_", "")
        return "Unknown"

    df["material_name"] = df.apply(get_material, axis=1)

    import plotly.express as px

    # Metrics
    df["co2_reduction"] = 100 - df["co2_emission_score"]
    df["cost_savings"] = 100 - df["cost"]

    graph1 = px.bar(df, x="material_name", y="co2_reduction",
                    title="CO₂ Reduction %").to_html(full_html=False, include_plotlyjs='cdn')

    graph2 = px.bar(df, x="material_name", y="cost_savings",
                    title="Cost Savings").to_html(full_html=False, include_plotlyjs='cdn')

    graph3 = px.histogram(df, x="material_name",
                          title="Material Usage Trends").to_html(full_html=False, include_plotlyjs='cdn')

    return render_template("dashboard.html",
                           graph1=graph1,
                           graph2=graph2,
                           graph3=graph3)

# -----------------------------
# RECOMMENDATION API (FINAL)
# -----------------------------
@app.route('/recommend', methods=['POST'])
def recommend():
    global last_results

    data = request.get_json()

    num = int(data.get("recommendations", 5))
    filter_type = data.get("filter", "score")

    # -----------------------------
    # SIMPLE INPUT CONVERSION
    # -----------------------------
    budget_map = {
        "low": 50,
        "medium": 100,
        "high": 9999
    }

    eco_map = {
        "low": 100,
        "medium": 70,
        "high": 40
    }

    durability_map = {
        "low": 0,
        "medium": 50,
        "high": 70
    }

    budget = budget_map.get(data.get("budget"), 100)
    eco = eco_map.get(data.get("eco"), 100)
    durability = durability_map.get(data.get("durability"), 0)

    # -----------------------------
    # FETCH DATA
    # -----------------------------
    conn = get_connection()
    df = pd.read_sql('SELECT * FROM material', conn)
    conn.close()

    # Detect material name
    def get_material(row):
        for col in df.columns:
            if col.startswith("material_type_") and row[col] == True:
                return col.replace("material_type_", "")
        return "Unknown"

    df["material_name"] = df.apply(get_material, axis=1)

    # -----------------------------
    # APPLY FILTERS
    # -----------------------------
    df = df[
        (df["cost"] <= budget) &
        (df["co2_emission_score"] <= eco) &
        (df["recyclability"] >= durability)
    ]

    # -----------------------------
    # SORTING
    # -----------------------------
    if filter_type == "cost":
        df = df.sort_values(by="cost", ascending=True)
    elif filter_type == "co2":
        df = df.sort_values(by="co2_emission_score", ascending=True)
    else:
        df = df.sort_values(by="Material_Suitability_Score", ascending=False)

    df = df.head(num)

    # STORE RESULTS
    last_results = df

    return jsonify({"recommendations": df.to_dict(orient="records")})

# -----------------------------
# DOWNLOAD CSV (RECOMMENDED ONLY)
# -----------------------------
@app.route('/download')
def download():
    global last_results

    if last_results is None or last_results.empty:
        return "No recommendations yet!"

    file_path = "recommended_materials.csv"
    last_results.to_csv(file_path, index=False)

    return send_file(file_path, as_attachment=True)

# -----------------------------
# DOWNLOAD PDF (RECOMMENDED ONLY)
# -----------------------------
@app.route('/download_pdf')
def download_pdf():
    global last_results

    if last_results is None or last_results.empty:
        return "No recommendations yet!"

    file_path = "recommended_materials.pdf"

    data = [list(last_results.columns)]
    for _, row in last_results.iterrows():
        data.append(list(row))

    pdf = SimpleDocTemplate(file_path)
    table = Table(data)
    pdf.build([table])

    return send_file(file_path, as_attachment=True)

# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)