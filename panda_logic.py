import pandas as pd
from fuzzywuzzy import process
import re


def is_numeric_column(series):
    return pd.api.types.is_numeric_dtype(series)


def extract_number(text):
    match = re.search(r'(-?\d+(?:\.\d+)?)', text)
    return match.group(1) if match else None


def get_best_column_match(user_text, columns, threshold=60):
    user_text = user_text.lower().strip()

    for col in columns:
        if col.lower() in user_text:
            return col

    best_match = None
    best_score = 0

    for col in columns:
        result = process.extractOne(user_text, [col])
        if result:
            match, score = result
            if score > best_score:
                best_match = match
                best_score = score

    if best_score >= threshold:
        return best_match

    words = re.findall(r'\w+', user_text)
    for word in words:
        result = process.extractOne(word, columns)
        if result:
            match, score = result
            if score > best_score:
                best_match = match
                best_score = score

    return best_match


def get_all_matching_columns(user_text, columns, threshold=70):
    matched = []

    for col in columns:
        if col.lower() in user_text.lower():
            matched.append(col)

    parts = re.split(r'and|,|with|along with', user_text.lower())
    for part in parts:
        part = part.strip()
        if not part:
            continue

        result = process.extractOne(part, columns)
        if result:
            match, score = result
            if score >= threshold and match not in matched:
                matched.append(match)

    return matched


def build_single_condition(condition_text, df):
    columns = df.columns.tolist()
    text = condition_text.lower().strip()

    col = get_best_column_match(text, columns)
    num = extract_number(text)

    if any(x in text for x in ["more than", "above", "greater than", "over", ">"]):
        if col and num and is_numeric_column(df[col]):
            return f"(df['{col}'] > {num})"

    if any(x in text for x in ["less than", "below", "under", "<"]):
        if col and num and is_numeric_column(df[col]):
            return f"(df['{col}'] < {num})"

    if any(x in text for x in ["equal to", "equals", "equal", "="]):
        if col and num and is_numeric_column(df[col]):
            return f"(df['{col}'] == {num})"

    match = re.search(r"(.+?)\s+(?:is|equals|=)\s+([a-zA-Z0-9+\- ]+)", text)
    if match:
        possible_col = match.group(1).strip()
        value = match.group(2).strip()
        col = get_best_column_match(possible_col, columns)
        if col:
            return f"(df['{col}'].astype(str).str.lower() == '{value.lower()}')"

    match = re.search(r"(.+?) contains ([a-zA-Z0-9 _+\-]+)", text)
    if match:
        possible_col = match.group(1).strip()
        value = match.group(2).strip()
        col = get_best_column_match(possible_col, columns)
        if col:
            return f"(df['{col}'].astype(str).str.lower().str.contains('{value.lower()}', na=False))"

    return None


def translate_to_query(nl_query, df):
    nl_query = nl_query.lower().strip()
    columns = df.columns.tolist()

    if nl_query in ["show all", "show all data", "all data", "display all"]:
        return "df"

    top_match = re.search(r"top (\d+)", nl_query)
    if top_match:
        n = int(top_match.group(1))
        col = get_best_column_match(nl_query, columns)
        if col and is_numeric_column(df[col]):
            return f"df.nlargest({n}, '{col}')"

    if any(x in nl_query for x in ["highest", "maximum", "max"]):
        col = get_best_column_match(nl_query, columns)
        if col and is_numeric_column(df[col]):
            return f"df[df['{col}'] == df['{col}'].max()]"

    if any(x in nl_query for x in ["lowest", "minimum", "min"]):
        col = get_best_column_match(nl_query, columns)
        if col and is_numeric_column(df[col]):
            return f"df[df['{col}'] == df['{col}'].min()]"

    if "sum of" in nl_query or nl_query.startswith("sum "):
        col = get_best_column_match(nl_query, columns)
        if col and is_numeric_column(df[col]):
            return f"df['{col}'].sum()"

    if "average" in nl_query or "mean" in nl_query:
        col = get_best_column_match(nl_query, columns)
        if col and is_numeric_column(df[col]):
            return f"df['{col}'].mean()"

    if nl_query == "count" or "count of" in nl_query or "number of rows" in nl_query:
        return "len(df)"

    group_match = re.search(r"(total|sum|average|mean|count)\s+(.+?)\s+by\s+(.+)", nl_query)
    if group_match:
        operation = group_match.group(1).strip()
        value_col_text = group_match.group(2).strip()
        group_col_text = group_match.group(3).strip()

        value_col = get_best_column_match(value_col_text, columns)
        group_col = get_best_column_match(group_col_text, columns)

        if group_col:
            if operation in ["total", "sum"] and value_col and is_numeric_column(df[value_col]):
                return f"df.groupby('{group_col}')['{value_col}'].sum().reset_index()"

            if operation in ["average", "mean"] and value_col and is_numeric_column(df[value_col]):
                return f"df.groupby('{group_col}')['{value_col}'].mean().reset_index()"

            if operation == "count":
                return f"df.groupby('{group_col}').size().reset_index(name='Count')"

    if "sort by" in nl_query or "sorted by" in nl_query or "order by" in nl_query:
        col = get_best_column_match(nl_query, columns)
        if col:
            descending_words = ["descending", "desc", "highest to lowest", "reverse"]
            ascending = not any(word in nl_query for word in descending_words)
            return f"df.sort_values(by='{col}', ascending={ascending})"

    if " and " in nl_query:
        parts = nl_query.split(" and ")
        conditions = []

        for part in parts:
            cond = build_single_condition(part, df)
            if cond:
                conditions.append(cond)

        if conditions:
            return f"df[{' & '.join(conditions)}]"

    single_condition = build_single_condition(nl_query, df)
    if single_condition:
        return f"df[{single_condition}]"

    if nl_query.startswith("show ") or nl_query.startswith("list ") or nl_query.startswith("display "):
        matched_cols = get_all_matching_columns(nl_query, columns)
        if matched_cols:
            cols_text = ", ".join([repr(col) for col in matched_cols])
            return f"df[[{cols_text}]]"

    return None


def process_query(df, user_query):
    pandas_query = translate_to_query(user_query, df)
    print("Generated Query:", pandas_query)

    if pandas_query is None:
        return None, "Query not understood. Try one of the suggestions below."

    try:
        result = eval(pandas_query)

        if isinstance(result, pd.DataFrame):
            if result.empty:
                return None, "No matching rows found."

            filename = "result.xlsx"
            result.to_excel("static/" + filename, index=False)

            table_html = result.to_html(classes="data-table", index=False)
            download_link = f'<br><a href="/static/{filename}" download class="download-btn">Download Result</a>'

            return table_html + download_link, None

        if isinstance(result, pd.Series):
            result_df = result.to_frame()
            filename = "result.xlsx"
            result_df.to_excel("static/" + filename, index=True)

            table_html = result_df.to_html(classes="data-table")
            download_link = f'<br><a href="/static/{filename}" download class="download-btn">Download Result</a>'

            return table_html + download_link, None

        return f"<div class='single-result'>{result}</div>", None

    except Exception as e:
        return None, f"Error executing query: {e}"


def generate_query_suggestions(columns):
    suggestions = []
    lower_cols = [col.lower() for col in columns]

    suggestions.append("show all data")
    suggestions.append("count")
    suggestions.append("show " + " and ".join(columns[:2]) if len(columns) >= 2 else f"show {columns[0]}")

    numeric_keywords = ["marks", "sales", "profit", "age", "quantity", "price", "score", "total"]
    numeric_cols = [col for col in columns if any(k in col.lower() for k in numeric_keywords)]

    if numeric_cols:
        suggestions.append(f"{numeric_cols[0].lower()} above 44")
        suggestions.append(f"{numeric_cols[0].lower()} below 44")
        suggestions.append(f"highest {numeric_cols[0].lower()}")
        suggestions.append(f"average {numeric_cols[0].lower()}")
        suggestions.append(f"top 5 {numeric_cols[0].lower()}")

    if "class" in lower_cols:
        suggestions.append("class is a")

    if "blood group" in lower_cols:
        suggestions.append("blood group is a+")

    if "region" in lower_cols:
        suggestions.append("region is south")

    if "product" in lower_cols:
        suggestions.append("product contains pen")

    if len(numeric_cols) >= 1:
        possible_group_cols = [col for col in columns if not any(k in col.lower() for k in numeric_keywords)]
        if possible_group_cols:
            suggestions.append(f"total {numeric_cols[0].lower()} by {possible_group_cols[0].lower()}")

    final_suggestions = []
    seen = set()
    for item in suggestions:
        if item not in seen:
            final_suggestions.append(item)
            seen.add(item)

    return final_suggestions[:10]