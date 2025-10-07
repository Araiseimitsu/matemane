import pandas as pd

df = pd.read_excel('材料管理.xlsx', sheet_name='材料管理表', engine='openpyxl')

def is_blank(val):
    if pd.isna(val):
        return True
    s = str(val).strip()
    return s == "" or s in {"-", "－", "—"}

# 各列の条件チェック
mask_i = ~df.iloc[:, 8].apply(is_blank)   # I列(品番)非空
mask_l = ~df.iloc[:, 11].apply(is_blank)  # L列(材料)非空
mask_z = ~df.iloc[:, 25].apply(is_blank)  # Z列(指定納期)非空
mask_ac = df.iloc[:, 28].apply(is_blank)  # AC列(入荷日)が空

# 全条件を満たす行
combined = mask_i & mask_l & mask_z & mask_ac

print(f'I列(品番)非空: {mask_i.sum()}')
print(f'L列(材料)非空: {mask_l.sum()}')
print(f'Z列(指定納期)非空: {mask_z.sum()}')
print(f'AC列(入荷日)が空: {mask_ac.sum()}')
print(f'\n全条件を満たす行数: {combined.sum()}')

if combined.sum() > 0:
    print(f'\n最初の5行（条件を満たす行）:')
    matching_rows = df[combined].head(5)
    print(matching_rows.iloc[:, [8, 11, 13, 25, 26, 28]])

    # 手配先と管理NOのチェック
    print(f'\n手配先(AA列)が空の行数: {matching_rows.iloc[:, 26].apply(is_blank).sum()}')
    print(f'管理NO(N列)が空の行数: {matching_rows.iloc[:, 13].apply(is_blank).sum()}')
