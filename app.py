from flask import Flask, render_template, request
import pandas as pd
from panda_logic import process_query, generate_query_suggestions

app = Flask(__name__)

df = None
columns = []
suggestions = []


@app.route("/", methods=["GET", "POST"])
def index():
    global df, columns, suggestions

    result = None
    error = None
    message = None

    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]

            if file and file.filename != "":
                try:
                    df = pd.read_excel(file)
                    df.columns = df.columns.str.strip()
                    columns = df.columns.tolist()
                    suggestions = generate_query_suggestions(columns)
                    message = "File uploaded successfully."
                    print("\nLoaded columns:")
                    print(columns)
                except Exception as e:
                    error = f"Error loading file: {e}"

        if "query" in request.form:
            query = request.form.get("query", "").strip()

            if df is None:
                error = "Please upload an Excel file first."
            elif not query:
                error = "Please enter a query."
            else:
                print("User Query:", query)
                result, error = process_query(df, query)

    return render_template(
        "index.html",
        result=result,
        error=error,
        message=message,
        columns=columns,
        suggestions=suggestions
    )


if __name__ == "__main__":
    app.run()