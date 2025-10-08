/**
 * APIクライアント
 * バックエンドとの通信を担当
 */
class APIClient {
  static baseURL = "/api";

  /**
   * HTTPリクエストの共通処理
   */
  static async request(url, options = {}) {
    const token = localStorage.getItem("access_token");

    const config = {
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        let message = `HTTP ${response.status}: ${response.statusText}`;
        if (errorData && errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            // FastAPIの422(Unprocessable Entity)などで返る詳細配列に対応
            message = errorData.detail
              .map((d) => d.msg || d?.message || JSON.stringify(d))
              .join(" | ");
          } else {
            message = errorData.detail;
          }
        }
        throw new Error(message);
      }

      return await response.json();
    } catch (error) {
      console.error("API Request Error:", error);
      throw error;
    }
  }

  /**
   * GETリクエスト
   */
  static async get(endpoint, params = {}) {
    const url = new URL(`${this.baseURL}${endpoint}`, window.location.origin);
    Object.keys(params).forEach((key) => {
      if (
        params[key] !== null &&
        params[key] !== undefined &&
        params[key] !== ""
      ) {
        url.searchParams.append(key, params[key]);
      }
    });

    return this.request(url.toString());
  }

  /**
   * POSTリクエスト
   */
  static async post(endpoint, data = {}) {
    return this.request(`${this.baseURL}${endpoint}`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  /**
   * PUTリクエスト
   */
  static async put(endpoint, data = {}) {
    return this.request(`${this.baseURL}${endpoint}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  /**
   * PATCHリクエスト
   */
  static async patch(endpoint, data = {}) {
    return this.request(`${this.baseURL}${endpoint}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  /**
   * DELETEリクエスト
   */
  static async delete(endpoint) {
    return this.request(`${this.baseURL}${endpoint}`, {
      method: "DELETE",
    });
  }

  // ===== 認証関連 =====

  /**
   * ログイン
   */
  static async login(username, password) {
    const formData = new FormData();
    formData.append("username", username);
    formData.append("password", password);

    const response = await fetch(`${this.baseURL}/auth/login`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || "ログインに失敗しました");
    }

    return response.json();
  }

  // ===== 材料管理 =====

  /**
   * 材料一覧取得
   */
  static async getMaterials(params = {}) {
    return this.get("/materials/", params);
  }

  /**
   * 材料総件数取得
   */
  static async getMaterialsCount(params = {}) {
    return this.get("/materials/count", params);
  }

  /**
   * 材料作成
   */
  static async createMaterial(data) {
    return this.post("/materials/", data);
  }

  /**
   * 材料更新
   */
  static async updateMaterial(id, data) {
    return this.put(`/materials/${id}`, data);
  }

  /**
   * 材料削除
   */
  static async deleteMaterial(id) {
    return this.delete(`/materials/${id}`);
  }

  // ===== 材料グループ =====

  /**
   * グループ一覧取得
   */
  static async getMaterialGroups(params = {}) {
    return this.get("/material-groups/", params);
  }

  /**
   * グループ作成
   */
  static async createMaterialGroup(data) {
    return this.post("/material-groups/", data);
  }

  /**
   * グループ更新
   */
  static async updateMaterialGroup(id, data) {
    return this.patch(`/material-groups/${id}`, data);
  }

  /**
   * グループ削除
   */
  static async deleteMaterialGroup(id) {
    return this.delete(`/material-groups/${id}`);
  }

  /**
   * グループメンバー一覧
   */
  static async getGroupMembers(groupId) {
    return this.get(`/material-groups/${groupId}/members`);
  }

  /**
   * グループメンバー追加
   */
  static async addGroupMember(groupId, materialId) {
    return this.post(`/material-groups/${groupId}/members`, { material_id: materialId });
  }

  /**
   * グループメンバー削除
   */
  static async removeGroupMember(groupId, memberId) {
    return this.delete(`/material-groups/${groupId}/members/${memberId}`);
  }

  // ===== 在庫管理 =====

  /**
   * 在庫一覧取得
   */
  static async getInventory(params = {}) {
    return this.get("/inventory/", params);
  }

  /**
   * 在庫サマリー取得
   */
  static async getInventorySummary(params = {}) {
    return this.get("/inventory/summary/", params);
  }

  /**
   * 在庫グループ集計取得
   */
  static async getInventoryGroups(params = {}) {
    return this.get("/inventory/groups", params);
  }

  /**
   * 管理コード検索
   */
  static async searchByManagementCode(code) {
    return this.get(`/inventory/search/${code}`);
  }

  /**
   * 在庫不足アイテム取得
   */
  static async getLowStockItems(threshold = 5) {
    return this.get("/inventory/low-stock/", { threshold });
  }

  // ===== 入出庫管理 =====

  /**
   * 入出庫履歴取得
   */
  static async getMovements(params = {}) {
    return this.get("/movements", params);
  }

  /**
   * 入庫処理
   */
  static async receiveItems(data) {
    return this.post("/movements/receive", data);
  }

  /**
   * 出庫処理
   */
  static async issueItems(data) {
    return this.post("/movements/issue", data);
  }

  /**
   * 戻し処理
   */
  static async returnItems(data) {
    return this.post("/movements/return", data);
  }

  /**
   * 移動処理
   */
  static async moveItems(data) {
    return this.post("/movements/move", data);
  }

  /**
   * アイテム検索（材料名や径などで絞り込み）
   */
  static async searchMovementItems(params = {}) {
    return this.get("/inventory/search", params);
  }

  /**
   * 入庫処理（アイテムIDベース）
   */
  static async inMovement(itemId, data) {
    return this.post(`/movements/in/${itemId}`, data);
  }

  /**
   * 出庫処理（アイテムIDベース）
   */
  static async outMovement(itemId, data) {
    return this.post(`/movements/out/${itemId}`, data);
  }

  /**
   * 置き場変更処理（アイテムIDベース）
   */
  static async relocateItem(itemId, data) {
    return this.put(`/movements/relocate/${itemId}`, data);
  }

  // ===== ラベル印刷 =====

  /**
   * ラベル印刷
   */
  static async printLabel(data) {
    return this.post("/labels/print", data);
  }

  // ===== 置き場管理 =====

  /**
   * 置き場一覧取得
   */
  static async getLocations(params = {}) {
    return this.get("/inventory/locations/", params);
  }

  // ===== 発注管理 =====

  /**
   * 発注一覧取得
   */
  static async getPurchaseOrders(params = {}) {
    return this.get("/purchase-orders/", params);
  }

  /**
   * 入庫待ちアイテム一覧取得
   */
  static async getPendingItems() {
    return this.get("/purchase-orders/pending/items/");
  }

  /**
   * 入庫待ち・検品待ちアイテム取得
   */
  static async getPendingPurchaseItems(includeInspected = false) {
    return this.get("/purchase-orders/pending-or-inspection/items/", {
      include_inspected: includeInspected,
    });
  }

  /**
   * 材料検索（名称・品番など）
   */
  static async searchMaterials(queryText) {
    return this.get("/materials/search/", { query_text: queryText });
  }

  // ===== 生産スケジュール =====

  /**
   * 在庫切れ予測取得
   */
  static async getStockoutForecast() {
    return this.get("/production-schedule/stockout-forecast");
  }
}

// グローバルに利用可能にする
window.APIClient = APIClient;
