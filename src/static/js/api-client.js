/**
 * APIクライアント
 * バックエンドとの通信を担当
 */
class APIClient {
    static baseURL = '/api';

    /**
     * HTTPリクエストの共通処理
     */
    static async request(url, options = {}) {
        const token = localStorage.getItem('access_token');

        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...(token && { 'Authorization': `Bearer ${token}` }),
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Request Error:', error);
            throw error;
        }
    }

    /**
     * GETリクエスト
     */
    static async get(endpoint, params = {}) {
        const url = new URL(`${this.baseURL}${endpoint}`, window.location.origin);
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
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
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * PUTリクエスト
     */
    static async put(endpoint, data = {}) {
        return this.request(`${this.baseURL}${endpoint}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETEリクエスト
     */
    static async delete(endpoint) {
        return this.request(`${this.baseURL}${endpoint}`, {
            method: 'DELETE'
        });
    }

    // ===== 認証関連 =====

    /**
     * ログイン
     */
    static async login(username, password) {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(`${this.baseURL}/auth/login`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'ログインに失敗しました');
        }

        return response.json();
    }

    // ===== 材料管理 =====

    /**
     * 材料一覧取得
     */
    static async getMaterials(params = {}) {
        return this.get('/materials/', params);
    }

    /**
     * 材料作成
     */
    static async createMaterial(data) {
        return this.post('/materials/', data);
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

    // ===== 在庫管理 =====

    /**
     * 在庫一覧取得
     */
    static async getInventory(params = {}) {
        return this.get('/inventory/', params);
    }

    /**
     * 在庫サマリー取得
     */
    static async getInventorySummary(params = {}) {
        return this.get('/inventory/summary/', params);
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
        return this.get('/inventory/low-stock/', { threshold });
    }

    // ===== 入出庫管理 =====

    /**
     * 入出庫履歴取得
     */
    static async getMovements(params = {}) {
        return this.get('/movements', params);
    }

    /**
     * 入庫処理
     */
    static async receiveItems(data) {
        return this.post('/movements/receive', data);
    }

    /**
     * 出庫処理
     */
    static async issueItems(data) {
        return this.post('/movements/issue', data);
    }

    /**
     * 戻し処理
     */
    static async returnItems(data) {
        return this.post('/movements/return', data);
    }

    /**
     * 移動処理
     */
    static async moveItems(data) {
        return this.post('/movements/move', data);
    }

    /**
     * アイテム検索（材料名や径などで絞り込み）
     */
    static async searchMovementItems(params = {}) {
        return this.get('/movements/search-items', params);
    }

    // ===== ラベル印刷 =====

    /**
     * ラベル印刷
     */
    static async printLabel(data) {
        return this.post('/labels/print', data);
    }

    // ===== 置き場管理 =====

    /**
     * 置き場一覧取得
     */
    static async getLocations(params = {}) {
        return this.get('/locations', params);
    }

    // ===== ロット管理 =====

    /**
     * ロット一覧取得
     */
    static async getLots(params = {}) {
        return this.get('/lots', params);
    }
}

// グローバルに利用可能にする
window.APIClient = APIClient;