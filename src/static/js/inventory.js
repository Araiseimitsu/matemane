// 在庫管理JavaScript機能

class InventoryManager {
    constructor() {
        this.inventoryItems = [];
        this.selectedItem = null;
        this.viewMode = 'list'; // 'list', 'summary'
        this.summaryMode = 'name'; // 既定はExcel完全同名での集計
        this.init();
    }

    init() {
        // URLクエリでサマリーモードを切り替え（例: ?summary_mode=length）
        const urlParams = new URLSearchParams(window.location.search);
        const mode = urlParams.get('summary_mode');
        if (mode === 'length') {
            this.summaryMode = 'length';
        }
        this.loadInventory();
        this.bindEvents();
        this.setupSearch();
    }

    // イベントバインディング
    bindEvents() {
        // 表示切り替えボタン
        const listViewBtn = document.getElementById('listViewBtn');
        const summaryViewBtn = document.getElementById('summaryViewBtn');

        if (listViewBtn) {
            listViewBtn.addEventListener('click', () => this.switchView('list'));
        }

        if (summaryViewBtn) {
            summaryViewBtn.addEventListener('click', () => this.switchView('summary'));
        }

        // 検索フォーム
        const searchForm = document.getElementById('inventorySearchForm');
        if (searchForm) {
            searchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.searchInventory();
            });
        }

        // リアルタイム検索
        const searchInputs = document.querySelectorAll('#inventorySearchForm input, #inventorySearchForm select');
        searchInputs.forEach(input => {
            input.addEventListener('input', () => this.debounceSearch());
        });

        // QRコード検索
        const qrSearchBtn = document.getElementById('qrSearchBtn');
        if (qrSearchBtn) {
            qrSearchBtn.addEventListener('click', () => this.openQRSearch());
        }

        // 管理コード検索
        const codeSearchBtn = document.getElementById('codeSearchBtn');
        if (codeSearchBtn) {
            codeSearchBtn.addEventListener('click', () => this.searchByCode());
        }

        // 低在庫アラート
        const lowStockBtn = document.getElementById('lowStockBtn');
        if (lowStockBtn) {
            lowStockBtn.addEventListener('click', () => this.showLowStock());
        }

        // エクスポート機能
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportInventory());
        }

        // モーダル関連
        const closeButtons = document.querySelectorAll('[data-dismiss="modal"]');
        closeButtons.forEach(btn => {
            btn.addEventListener('click', () => this.closeModal());
        });

        // ラベル印刷
        const printLabelBtns = document.querySelectorAll('[data-action="print-label"]');
        printLabelBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const managementCode = e.currentTarget.dataset.managementCode;
                this.printLabel(managementCode);
            });
        });
    }

    // 検索機能セットアップ
    setupSearch() {
        this.resetSearch();
    }

    // 在庫一覧読み込み
    async loadInventory(filters = {}) {
        try {
            this.showLoading();
            const params = new URLSearchParams();

            Object.keys(filters).forEach(key => {
                if (filters[key] !== null && filters[key] !== '') {
                    params.append(key, filters[key]);
                }
            });

            let endpoint = '/api/inventory';
            if (this.viewMode === 'summary') {
                endpoint = this.summaryMode === 'name' ? '/api/inventory/summary-by-name' : '/api/inventory/summary';
            }
            const response = await fetch(`${endpoint}?${params}`);

            if (!response.ok) {
                throw new Error('在庫データの取得に失敗しました');
            }

            this.inventoryItems = await response.json();
            this.renderInventory();
            this.showToast('在庫一覧を更新しました', 'success');
        } catch (error) {
            console.error('Error loading inventory:', error);
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    // 表示モード切り替え
    switchView(mode) {
        this.viewMode = mode;

        // ボタン状態更新
        document.getElementById('listViewBtn')?.classList.toggle('bg-blue-600', mode === 'list');
        document.getElementById('listViewBtn')?.classList.toggle('bg-gray-200', mode !== 'list');
        document.getElementById('summaryViewBtn')?.classList.toggle('bg-blue-600', mode === 'summary');
        document.getElementById('summaryViewBtn')?.classList.toggle('bg-gray-200', mode !== 'summary');

        this.loadInventory();
    }

    // 在庫表示
    renderInventory() {
        const container = document.getElementById('inventoryContainer');
        if (!container) return;

        if (this.inventoryItems.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12 text-gray-500">
                    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2M4 13h2m13-8L6 5V8a2 2 0 002 2h8a2 2 0 002-2V8" />
                    </svg>
                    <p class="text-lg mt-4">在庫データがありません</p>
                    <p class="text-sm mt-2">検索条件を変更するか、新しい材料を登録してください</p>
                </div>
            `;
            return;
        }

        if (this.viewMode === 'list') {
            this.renderInventoryList();
        } else {
            this.renderInventorySummary();
        }
    }

    // リスト表示
    renderInventoryList() {
        const container = document.getElementById('inventoryContainer');
        const html = this.inventoryItems.map(item => this.renderInventoryCard(item)).join('');
        container.innerHTML = html;
    }

    // 在庫カード描画
    renderInventoryCard(item) {
        const shapeNames = {
            'round': '丸棒',
            'hexagon': '六角棒',
            'square': '角棒'
        };

        const stockStatus = this.getStockStatus(item.current_quantity);
        const locationName = item.location ? item.location.name : '未配置';

        return `
            <div class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow border-l-4 ${stockStatus.borderColor}">
                <div class="flex justify-between items-start mb-4">
                    <div class="flex-1">
                        <h3 class="text-lg font-semibold text-gray-800">${item.material.display_name || item.material.name}</h3>
                        <p class="text-sm text-gray-600">ロット: ${item.lot.lot_number}</p>
                        <p class="text-sm text-gray-600">管理コード: ${item.management_code}</p>
                    </div>
                    <div class="flex space-x-2">
                        <button onclick="inventoryManager.showItemDetail('${item.management_code}')"
                                class="text-blue-600 hover:text-blue-800 p-1">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                            </svg>
                        </button>
                        <button onclick="inventoryManager.printLabel('${item.management_code}')"
                                class="text-green-600 hover:text-green-800 p-1">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path>
                            </svg>
                        </button>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4 text-sm mb-4">
                    <div>
                        <span class="text-gray-600">形状:</span>
                        <span class="font-medium">${shapeNames[item.material.shape] || item.material.shape}</span>
                    </div>
                    <div>
                        <span class="text-gray-600">寸法:</span>
                        <span class="font-medium">φ${item.material.diameter_mm}mm</span>
                    </div>
                    <div>
                        <span class="text-gray-600">長さ:</span>
                        <span class="font-medium">${item.lot.length_mm}mm</span>
                    </div>
                    <div>
                        <span class="text-gray-600">置き場:</span>
                        <span class="font-medium">${locationName}</span>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4 text-sm mb-4 p-3 bg-gray-50 rounded">
                    <div class="text-center">
                        <div class="text-2xl font-bold ${stockStatus.textColor}">${item.current_quantity}</div>
                        <div class="text-gray-600">本</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-blue-600">${item.total_weight_kg}</div>
                        <div class="text-gray-600">kg</div>
                    </div>
                </div>

                <div class="flex space-x-2">
                    <button onclick="inventoryManager.initiateMovement('${item.management_code}', 'out')"
                            class="flex-1 bg-red-100 text-red-700 py-2 px-4 rounded hover:bg-red-200 transition-colors">
                        出庫
                    </button>
                    <button onclick="inventoryManager.initiateMovement('${item.management_code}', 'in')"
                            class="flex-1 bg-green-100 text-green-700 py-2 px-4 rounded hover:bg-green-200 transition-colors">
                        入庫
                    </button>
                </div>
            </div>
        `;
    }

    // サマリー表示
    renderInventorySummary() {
        const container = document.getElementById('inventoryContainer');
        const html = this.inventoryItems.map(item => this.renderSummaryCard(item)).join('');
        container.innerHTML = html;
    }

    // サマリーカード描画
    renderSummaryCard(item) {
        const shapeNames = {
            'round': '丸棒',
            'hexagon': '六角棒',
            'square': '角棒'
        };

        // name-onlyモードのレスポンスには寸法・長さが含まれないため表示を分岐
        const isNameOnly = (this.summaryMode === 'name') || (item.length_mm === undefined);

        if (isNameOnly) {
            return `
            <div class="bg-white rounded-lg shadow-md p-6">
                <div class="mb-4">
                    <h3 class="text-lg font-semibold text-gray-800">${item.material_name}</h3>
                    <p class="text-sm text-gray-600">材質名のみで集計（長さ・寸法無視）</p>
                </div>

                <div class="grid grid-cols-2 gap-4 text-center">
                    <div class="bg-blue-50 p-4 rounded">
                        <div class="text-2xl font-bold text-blue-600">${item.total_quantity}</div>
                        <div class="text-sm text-gray-600">総本数</div>
                    </div>
                    <div class="bg-green-50 p-4 rounded">
                        <div class="text-2xl font-bold text-green-600">${item.total_weight_kg}</div>
                        <div class="text-sm text-gray-600">総重量(kg)</div>
                    </div>
                </div>

                <div class="mt-4 text-sm text-gray-600">
                    <div class="flex justify-between">
                        <span>ロット数:</span>
                        <span class="font-medium">${item.lot_count}</span>
                    </div>
                    <div class="flex justify-between">
                        <span>置き場数:</span>
                        <span class="font-medium">${item.location_count}</span>
                    </div>
                    <div class="flex justify-between">
                        <span>寸法バリエーション:</span>
                        <span class="font-medium">${item.diameter_variations ?? '-'}</span>
                    </div>
                    <div class="flex justify-between">
                        <span>長さバリエーション:</span>
                        <span class="font-medium">${item.length_variations ?? '-'}</span>
                    </div>
                </div>
            </div>
            `;
        }

        return `
            <div class="bg-white rounded-lg shadow-md p-6">
                <div class="mb-4">
                    <h3 class="text-lg font-semibold text-gray-800">${item.material_name}</h3>
                    <p class="text-sm text-gray-600">${shapeNames[item.material_shape]} φ${item.diameter_mm}mm × ${item.length_mm}mm</p>
                </div>

                <div class="grid grid-cols-2 gap-4 text-center">
                    <div class="bg-blue-50 p-4 rounded">
                        <div class="text-2xl font-bold text-blue-600">${item.total_quantity}</div>
                        <div class="text-sm text-gray-600">総本数</div>
                    </div>
                    <div class="bg-green-50 p-4 rounded">
                        <div class="text-2xl font-bold text-green-600">${item.total_weight_kg}</div>
                        <div class="text-sm text-gray-600">総重量(kg)</div>
                    </div>
                </div>

                <div class="mt-4 text-sm text-gray-600">
                    <div class="flex justify-between">
                        <span>ロット数:</span>
                        <span class="font-medium">${item.lot_count}</span>
                    </div>
                    <div class="flex justify-between">
                        <span>置き場数:</span>
                        <span class="font-medium">${item.location_count}</span>
                    </div>
                </div>
            </div>
        `;
    }

    // 在庫状況判定
    getStockStatus(quantity) {
        if (quantity === 0) {
            return {
                textColor: 'text-red-600',
                borderColor: 'border-red-500',
                status: '在庫切れ'
            };
        } else if (quantity <= 5) {
            return {
                textColor: 'text-yellow-600',
                borderColor: 'border-yellow-500',
                status: '在庫少'
            };
        } else {
            return {
                textColor: 'text-green-600',
                borderColor: 'border-green-500',
                status: '在庫有'
            };
        }
    }

    // 検索実行
    async searchInventory() {
        const formData = new FormData(document.getElementById('inventorySearchForm'));
        const filters = Object.fromEntries(formData.entries());

        // 空の値を除外
        Object.keys(filters).forEach(key => {
            if (filters[key] === '') {
                delete filters[key];
            }
        });

        await this.loadInventory(filters);
    }

    // 検索デバウンス
    debounceSearch() {
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.searchInventory();
        }, 300);
    }

    // 検索リセット
    resetSearch() {
        const form = document.getElementById('inventorySearchForm');
        if (form) {
            form.reset();
        }
        this.loadInventory();
    }

    // 管理コード検索
    async searchByCode() {
        const codeInput = document.getElementById('managementCodeInput');
        const managementCode = codeInput?.value?.trim();

        if (!managementCode) {
            this.showToast('管理コードを入力してください', 'error');
            return;
        }

        try {
            const response = await fetch(`/api/inventory/search/${managementCode}`);
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('指定された管理コードのアイテムが見つかりません');
                }
                throw new Error('検索に失敗しました');
            }

            const item = await response.json();
            this.showItemDetail(managementCode, item);
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // アイテム詳細表示
    async showItemDetail(managementCode, itemData = null) {
        try {
            let item = itemData;

            if (!item) {
                const response = await fetch(`/api/inventory/search/${managementCode}`);
                if (!response.ok) {
                    throw new Error('アイテム詳細の取得に失敗しました');
                }
                item = await response.json();
            }

            this.selectedItem = item;
            this.populateItemDetail(item);
            this.showModal('itemDetailModal');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // アイテム詳細データ設定
    populateItemDetail(item) {
        const shapeNames = {
            'round': '丸棒',
            'hexagon': '六角棒',
            'square': '角棒'
        };

        document.getElementById('detailMaterialName').textContent = item.material.display_name || item.material.name;
        document.getElementById('detailManagementCode').textContent = item.item.management_code;
        document.getElementById('detailShape').textContent = shapeNames[item.material.shape] || item.material.shape;
        document.getElementById('detailDiameter').textContent = `${item.material.diameter_mm}mm`;
        document.getElementById('detailLength').textContent = `${item.lot.length_mm}mm`;
        document.getElementById('detailLotNumber').textContent = item.lot.lot_number;
        document.getElementById('detailCurrentQuantity').textContent = `${item.item.current_quantity}本`;
        document.getElementById('detailWeightPerPiece').textContent = `${item.weight_per_piece_kg}kg`;
        document.getElementById('detailTotalWeight').textContent = `${item.total_weight_kg}kg`;
        document.getElementById('detailLocation').textContent = item.location ? item.location.name : '未配置';
        document.getElementById('detailSupplier').textContent = item.lot.supplier || '未登録';

        if (item.lot.received_date) {
            const date = new Date(item.lot.received_date);
            document.getElementById('detailReceivedDate').textContent = date.toLocaleDateString('ja-JP');
        } else {
            document.getElementById('detailReceivedDate').textContent = '未登録';
        }
    }

    // 入出庫開始
    initiateMovement(managementCode, type) {
        // movements.jsの機能を呼び出し
        if (window.movementManager) {
            window.movementManager.initMovement(managementCode, type);
        } else {
            // 入出庫管理ページに遷移
            window.location.href = `/movements?code=${managementCode}&type=${type}`;
        }
    }

    // ラベル印刷
    async printLabel(managementCode, labelType = 'standard') {
        try {
            const response = await fetch('/api/labels/print', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    management_code: managementCode,
                    label_type: labelType,
                    copies: 1
                })
            });

            if (!response.ok) {
                throw new Error('ラベル印刷に失敗しました');
            }

            // PDFダウンロード
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `label_${managementCode}_${new Date().toISOString().slice(0, 10)}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            this.showToast('ラベルを印刷しました', 'success');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // 低在庫アラート表示
    async showLowStock() {
        try {
            const threshold = document.getElementById('lowStockThreshold')?.value || 5;
            const response = await fetch(`/api/inventory/low-stock?threshold=${threshold}`);

            if (!response.ok) {
                throw new Error('低在庫データの取得に失敗しました');
            }

            const data = await response.json();
            this.displayLowStockAlert(data);
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // 低在庫アラート表示
    displayLowStockAlert(data) {
        const container = document.getElementById('lowStockContainer');
        if (!container) return;

        if (data.items.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-green-600">
                    <svg class="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <p class="text-lg mt-4">低在庫のアイテムはありません</p>
                </div>
            `;
        } else {
            const html = data.items.map(item => `
                <div class="border-l-4 ${this.getAlertColor(item.alert_level)} bg-white p-4 rounded shadow-sm">
                    <div class="flex justify-between items-start">
                        <div>
                            <h4 class="font-semibold">${item.material_name}</h4>
                            <p class="text-sm text-gray-600">ロット: ${item.lot_number}</p>
                            <p class="text-sm text-gray-600">置き場: ${item.location_name}</p>
                        </div>
                        <div class="text-right">
                            <div class="text-2xl font-bold ${this.getTextColor(item.alert_level)}">${item.current_quantity}</div>
                            <div class="text-sm text-gray-600">本</div>
                        </div>
                    </div>
                    <div class="mt-2">
                        <span class="inline-block px-2 py-1 text-xs font-semibold rounded ${this.getBadgeColor(item.alert_level)}">
                            ${item.alert_level}
                        </span>
                    </div>
                </div>
            `).join('');
            container.innerHTML = html;
        }

        this.showModal('lowStockModal');
    }

    // アラートレベル用色指定
    getAlertColor(level) {
        switch (level) {
            case '危険': return 'border-red-500';
            case '注意': return 'border-yellow-500';
            case '警告': return 'border-orange-500';
            default: return 'border-gray-300';
        }
    }

    getTextColor(level) {
        switch (level) {
            case '危険': return 'text-red-600';
            case '注意': return 'text-yellow-600';
            case '警告': return 'text-orange-600';
            default: return 'text-gray-600';
        }
    }

    getBadgeColor(level) {
        switch (level) {
            case '危険': return 'bg-red-100 text-red-800';
            case '注意': return 'bg-yellow-100 text-yellow-800';
            case '警告': return 'bg-orange-100 text-orange-800';
            default: return 'bg-gray-100 text-gray-800';
        }
    }

    // QRコード検索開始
    openQRSearch() {
        if (window.qrScanner) {
            window.qrScanner.startScan((code) => {
                this.searchByCode(code);
            });
        } else {
            this.showToast('QRスキャナーが利用できません', 'error');
        }
    }

    // エクスポート機能
    async exportInventory() {
        try {
            const filters = {}; // 現在の検索条件を取得
            const params = new URLSearchParams();

            Object.keys(filters).forEach(key => {
                if (filters[key] !== null && filters[key] !== '') {
                    params.append(key, filters[key]);
                }
            });

            const response = await fetch(`/api/inventory/export?${params}`);
            if (!response.ok) {
                throw new Error('エクスポートに失敗しました');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `inventory_${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            this.showToast('在庫データをエクスポートしました', 'success');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // モーダル表示
    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        }
    }

    // モーダル非表示
    closeModal() {
        const modals = document.querySelectorAll('[id$="Modal"]');
        modals.forEach(modal => {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        });
    }

    // ローディング表示
    showLoading() {
        const loader = document.getElementById('inventoryLoading');
        if (loader) {
            loader.classList.remove('hidden');
        }
    }

    // ローディング非表示
    hideLoading() {
        const loader = document.getElementById('inventoryLoading');
        if (loader) {
            loader.classList.add('hidden');
        }
    }

    // トースト通知
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const bgColor = {
            'success': 'bg-green-500',
            'error': 'bg-red-500',
            'warning': 'bg-yellow-500',
            'info': 'bg-blue-500'
        }[type] || 'bg-blue-500';

        toast.className = `fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg z-50 transform transition-transform duration-300 translate-x-full`;
        toast.textContent = message;

        document.body.appendChild(toast);

        // アニメーション
        setTimeout(() => {
            toast.classList.remove('translate-x-full');
        }, 100);

        // 自動削除
        setTimeout(() => {
            toast.classList.add('translate-x-full');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 3000);
    }
}

// グローバル変数として初期化
let inventoryManager;

// DOM読み込み完了後に初期化
document.addEventListener('DOMContentLoaded', () => {
    inventoryManager = new InventoryManager();
});