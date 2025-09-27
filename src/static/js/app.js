// 材料管理システム メインJavaScript

// グローバル設定
const API_BASE_URL = '/api';
const QR_SCAN_TIMEOUT = 30000; // 30秒

// ユーティリティ関数
class Utils {
    // トースト通知を表示
    static showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="flex items-center">
                <div class="flex-1">
                    <p class="text-sm font-medium">${message}</p>
                </div>
                <button class="ml-4 text-gray-400 hover:text-gray-600" onclick="this.parentElement.parentElement.parentElement.remove()">
                    <span class="sr-only">閉じる</span>
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                    </svg>
                </button>
            </div>
        `;

        document.body.appendChild(toast);

        // アニメーション表示
        setTimeout(() => toast.classList.add('show'), 100);

        // 5秒後に自動削除
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    // ローディング状態の管理
    static setLoading(element, loading = true) {
        if (loading) {
            element.disabled = true;
            const spinner = document.createElement('span');
            spinner.className = 'spinner mr-2';
            element.insertBefore(spinner, element.firstChild);
            element.dataset.originalText = element.textContent;
            element.lastChild.textContent = ' 処理中...';
        } else {
            element.disabled = false;
            const spinner = element.querySelector('.spinner');
            if (spinner) spinner.remove();
            if (element.dataset.originalText) {
                element.textContent = element.dataset.originalText;
                delete element.dataset.originalText;
            }
        }
    }

    // 重量計算
    static calculateWeight(shape, diameterMm, lengthMm, density, quantity = 1) {
        let volumeCm3 = 0;
        const radiusCm = (diameterMm / 2) / 10;
        const lengthCm = lengthMm / 10;

        switch (shape) {
            case 'round':
                volumeCm3 = Math.PI * Math.pow(radiusCm, 2) * lengthCm;
                break;
            case 'hexagon':
                const sideCm = (diameterMm / 2) / 10;
                volumeCm3 = (3 * Math.sqrt(3) / 2) * Math.pow(sideCm, 2) * lengthCm;
                break;
            case 'square':
                const sideLength = diameterMm / 10;
                volumeCm3 = Math.pow(sideLength, 2) * lengthCm;
                break;
        }

        const weightPerPieceKg = (volumeCm3 * density) / 1000;
        return {
            volumeCm3: Math.round(volumeCm3 * 1000) / 1000,
            weightPerPieceKg: Math.round(weightPerPieceKg * 1000) / 1000,
            totalWeightKg: Math.round(weightPerPieceKg * quantity * 1000) / 1000
        };
    }

    // 指示書番号の検証
    static validateInstructionNumber(instructionNumber) {
        const pattern = /^IS-\d{4}-\d{4}$/;
        return pattern.test(instructionNumber);
    }

    // 数値フォーマット
    static formatNumber(number, decimals = 0) {
        return new Intl.NumberFormat('ja-JP', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }).format(number);
    }
}

// APIクライアント
class APIClient {
    static async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Request Error:', error);
            throw error;
        }
    }

    // 材料関連API
    static async getMaterials(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/materials?${queryString}`);
    }

    static async createMaterial(materialData) {
        return this.request('/materials', {
            method: 'POST',
            body: JSON.stringify(materialData)
        });
    }

    static async calculateWeight(materialId, lengthMm, quantity = 1) {
        return this.request(`/materials/${materialId}/calculate-weight?length_mm=${lengthMm}&quantity=${quantity}`);
    }

    // 在庫関連API
    static async getInventory(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/inventory?${queryString}`);
    }

    static async searchByManagementCode(code) {
        return this.request(`/inventory/search/${code}`);
    }

    static async getLowStockItems(threshold = 5) {
        return this.request(`/inventory/low-stock?threshold=${threshold}`);
    }

    // 入出庫関連API
    static async createInMovement(itemId, movementData) {
        return this.request(`/movements/in/${itemId}`, {
            method: 'POST',
            body: JSON.stringify(movementData)
        });
    }

    static async createOutMovement(itemId, movementData) {
        return this.request(`/movements/out/${itemId}`, {
            method: 'POST',
            body: JSON.stringify(movementData)
        });
    }

    static async getMovementsByInstruction(instructionNumber) {
        return this.request(`/movements/by-instruction/${instructionNumber}`);
    }
}

// QRスキャナー
class QRScanner {
    constructor(videoElement, onScanSuccess, onScanError) {
        this.video = videoElement;
        this.onScanSuccess = onScanSuccess;
        this.onScanError = onScanError;
        this.stream = null;
        this.isScanning = false;
        this.timeoutId = null;
    }

    async start() {
        try {
            // カメラアクセス許可を要求
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'environment', // 背面カメラを優先
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            });

            this.video.srcObject = this.stream;
            this.isScanning = true;

            // タイムアウト設定
            this.timeoutId = setTimeout(() => {
                this.stop();
                this.onScanError('スキャンがタイムアウトしました');
            }, QR_SCAN_TIMEOUT);

            // QRコード検出（実際の実装では専用ライブラリを使用）
            this.video.addEventListener('loadedmetadata', () => {
                this.video.play();
                this.detectQRCode();
            });

        } catch (error) {
            console.error('カメラアクセスエラー:', error);
            this.onScanError('カメラにアクセスできません');
        }
    }

    stop() {
        this.isScanning = false;

        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }

        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        if (this.video.srcObject) {
            this.video.srcObject = null;
        }
    }

    detectQRCode() {
        if (!this.isScanning) return;

        // 実際の実装では、jsQRやZXingライブラリを使用してQR解析
        // ここでは簡略化のためにダミー実装

        // 定期的にQR検出を試行
        setTimeout(() => {
            if (this.isScanning) {
                this.detectQRCode();
            }
        }, 100);
    }

    // 手動でQRコードをシミュレート（開発用）
    simulateQRScan(code) {
        if (this.isScanning) {
            this.stop();
            this.onScanSuccess(code);
        }
    }
}

// フォーム管理
class FormManager {
    constructor(formElement) {
        this.form = formElement;
        this.setupValidation();
    }

    setupValidation() {
        // リアルタイムバリデーション
        const inputs = this.form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', () => this.validateField(input));
            input.addEventListener('input', () => this.clearFieldError(input));
        });

        // フォーム送信時の処理
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });
    }

    validateField(field) {
        const value = field.value.trim();
        let isValid = true;
        let errorMessage = '';

        // 必須チェック
        if (field.hasAttribute('required') && !value) {
            isValid = false;
            errorMessage = 'この項目は必須です';
        }

        // 指示書番号の形式チェック
        if (field.name === 'instruction_number' && value && !Utils.validateInstructionNumber(value)) {
            isValid = false;
            errorMessage = '指示書番号はIS-YYYY-NNNN形式で入力してください';
        }

        // 数値チェック
        if (field.type === 'number' && value && isNaN(value)) {
            isValid = false;
            errorMessage = '有効な数値を入力してください';
        }

        this.setFieldError(field, isValid ? null : errorMessage);
        return isValid;
    }

    setFieldError(field, message) {
        const existingError = field.parentNode.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }

        if (message) {
            field.classList.add('border-red-500');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'field-error text-red-500 text-sm mt-1';
            errorDiv.textContent = message;
            field.parentNode.appendChild(errorDiv);
        } else {
            field.classList.remove('border-red-500');
        }
    }

    clearFieldError(field) {
        if (field.classList.contains('border-red-500')) {
            this.setFieldError(field, null);
        }
    }

    async handleSubmit() {
        // 全フィールドのバリデーション
        const inputs = this.form.querySelectorAll('input, select, textarea');
        let isFormValid = true;

        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isFormValid = false;
            }
        });

        if (!isFormValid) {
            Utils.showToast('入力内容に誤りがあります', 'error');
            return;
        }

        const submitButton = this.form.querySelector('button[type="submit"]');
        Utils.setLoading(submitButton, true);

        try {
            const formData = new FormData(this.form);
            const data = Object.fromEntries(formData.entries());

            // カスタム送信処理を実行
            if (this.form.dataset.submitHandler) {
                await window[this.form.dataset.submitHandler](data);
            }

        } catch (error) {
            console.error('Form submission error:', error);
            Utils.showToast(error.message || 'エラーが発生しました', 'error');
        } finally {
            Utils.setLoading(submitButton, false);
        }
    }
}

// データテーブル管理
class DataTable {
    constructor(tableElement, options = {}) {
        this.table = tableElement;
        this.options = {
            sortable: true,
            filterable: true,
            pageSize: 20,
            ...options
        };
        this.currentPage = 1;
        this.sortColumn = null;
        this.sortDirection = 'asc';
        this.filterText = '';

        this.init();
    }

    init() {
        if (this.options.sortable) {
            this.setupSorting();
        }

        if (this.options.filterable) {
            this.setupFiltering();
        }

        this.setupPagination();
    }

    setupSorting() {
        const headers = this.table.querySelectorAll('th[data-sortable]');
        headers.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', () => {
                const column = header.dataset.sortable;
                if (this.sortColumn === column) {
                    this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    this.sortColumn = column;
                    this.sortDirection = 'asc';
                }
                this.applySort();
            });
        });
    }

    setupFiltering() {
        // フィルター入力欄を作成
        const filterContainer = document.createElement('div');
        filterContainer.className = 'mb-4';
        filterContainer.innerHTML = `
            <input type="text"
                   class="form-input w-full max-w-md"
                   placeholder="検索..."
                   id="table-filter-${this.table.id}">
        `;

        this.table.parentNode.insertBefore(filterContainer, this.table);

        const filterInput = filterContainer.querySelector('input');
        filterInput.addEventListener('input', (e) => {
            this.filterText = e.target.value.toLowerCase();
            this.applyFilter();
        });
    }

    setupPagination() {
        // ページネーション実装
    }

    applySort() {
        // ソート実装
    }

    applyFilter() {
        const rows = this.table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            const shouldShow = text.includes(this.filterText);
            row.style.display = shouldShow ? '' : 'none';
        });
    }

    refresh(data) {
        // テーブルデータの更新
        const tbody = this.table.querySelector('tbody');
        tbody.innerHTML = data.map(item => this.renderRow(item)).join('');
    }

    renderRow(item) {
        // 行のHTMLを生成（サブクラスで実装）
        return '<tr><td>実装してください</td></tr>';
    }
}

// アプリケーション初期化
document.addEventListener('DOMContentLoaded', () => {
    // フォーム管理の初期化
    const forms = document.querySelectorAll('form[data-form-manager]');
    forms.forEach(form => new FormManager(form));

    // データテーブルの初期化
    const tables = document.querySelectorAll('table[data-table]');
    tables.forEach(table => new DataTable(table));

    // グローバルイベントリスナー
    window.addEventListener('unhandledrejection', (event) => {
        console.error('Unhandled promise rejection:', event.reason);
        Utils.showToast('予期しないエラーが発生しました', 'error');
    });

    // サービスワーカーの登録（PWA対応準備）
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(err => {
            console.log('Service worker registration failed:', err);
        });
    }
});

// グローバルに公開
window.Utils = Utils;
window.APIClient = APIClient;
window.QRScanner = QRScanner;
window.FormManager = FormManager;
window.DataTable = DataTable;