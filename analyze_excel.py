import pandas as pd
import sys

def analyze_excel():
    try:
        # Excelファイルを読み込み
        df = pd.read_excel('セット予定表.xlsx', sheet_name='セット予定')

        print(f"Excel行数: {len(df)}")
        print(f"Excel列数: {len(df.columns)}")
        print("\n列名一覧:")
        for i, col in enumerate(df.columns):
            print(f"  {i}: {col}")

        # AA列（列インデックス27）が存在するかチェック
        if len(df.columns) > 27:
            aa_col = df.iloc[:, 27]  # AA列（0ベース）
            print(f"\nAA列（列インデックス27）のサンプル:")
            print(aa_col.head(10))
            print(f"\nAA列の値の種類:")
            print(aa_col.value_counts().head(10))
        else:
            print(f"\nAA列が存在しません。最大列数: {len(df.columns)}")

        # 重要な列（D, I, L, AA）の内容確認
        important_cols = {
            'D': 3,   # セット予定日
            'I': 8,   # 品番
            'L': 11,  # 材質/材料径
            'AA': 27  # 必要本数
        }

        print(f"\n重要な列の内容確認:")
        for col_name, col_idx in important_cols.items():
            if col_idx < len(df.columns):
                col_data = df.iloc[:, col_idx]
                print(f"\n{col_name}列（インデックス{col_idx}）:")
                print(f"  非NULL値数: {col_data.notna().sum()}")
                print(f"  サンプル値:")
                valid_values = col_data.dropna().head(5)
                for val in valid_values:
                    print(f"    {val}")
            else:
                print(f"\n{col_name}列（インデックス{col_idx}）: 存在しません")

    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    analyze_excel()