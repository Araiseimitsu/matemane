// 入出庫管理JavaScript機能

class MovementManager {
    constructor() {
        this.movements = [];
        this.selectedItem = null;
        this.currentMovementType = null;
        this.init();
    }

    init() {
        this.loadMovements();
        this.bindEvents();
        this.initializeFromParams();
    }

    // URLパラメータから初期化
    initializeFromParams() {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const type = urlParams.get('type');

        if (code && type) {
            this.initMovement(code, type);
        }
    }

    // イベントバインディング
    bindEvents() {
        // 入出庫履歴検索
        const searchForm = document.getElementById('movementSearchForm');
        if (searchForm) {
            searchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.searchMovements();
            });
        }

        // リアルタイム検索
        const searchInputs = document.querySelectorAll('#movementSearchForm input, #movementSearchForm select');
        searchInputs.forEach(input => {
            input.addEventListener('input', () => this.debounceSearch());
        });

        // QRスキャンボタン
        const qrScanBtn = document.getElementById('qrScanBtn');
        if (qrScanBtn) {
            qrScanBtn.addEventListener('click', () => this.startQRScan());
        }

        // 管理コード検索
        const codeSearchBtn = document.getElementById('codeSearchBtn');
        if (codeSearchBtn) {
            codeSearchBtn.addEventListener('click', () => this.searchByCode());
        }

        // 入出庫フォーム
        const movementForm = document.getElementById('movementForm');
        if (movementForm) {
            movementForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitMovement();
            });
        }

        // 指示書番号検索
        const instructionSearchBtn = document.getElementById('instructionSearchBtn');
        if (instructionSearchBtn) {
            instructionSearchBtn.addEventListener('click', () => this.searchByInstruction());
        }

        // 重量・本数の自動換算
        const quantityInput = document.getElementById('movementQuantity');
        const weightInput = document.getElementById('movementWeight');

        if (quantityInput) {
            quantityInput.addEventListener('input', () => this.calculateFromQuantity());
        }

        if (weightInput) {
            weightInput.addEventListener('input', () => this.calculateFromWeight());
        }

        // モーダル関連
        const closeButtons = document.querySelectorAll('[data-dismiss="modal"]');
        closeButtons.forEach(btn => {
            btn.addEventListener('click', () => this.closeModal());
        });

        // 入庫・出庫ボタン
        const inBtn = document.getElementById('startInBtn');
        const outBtn = document.getElementById('startOutBtn');

        if (inBtn) {
            // 変更: 入庫は受入れページへ誘導
            inBtn.addEventListener('click', () => {
                this.showToast('入庫は「入庫確認」ページで実施します', 'info');
                window.location.href = '/receiving';
            });
        }

        if (outBtn) {
            outBtn.addEventListener('click', () => this.showMovementTypeSelection('out'));
        }
    }

    // 入出庫履歴読み込み
    async loadMovements(filters = {}) {
        try {
            this.showLoading();
            const params = new URLSearchParams();

            Object.keys(filters).forEach(key => {
                if (filters[key] !== null && filters[key] !== '') {
                    params.append(key, filters[key]);
                }
            });

            const response = await fetch(`/api/movements?${params}`);
            if (!response.ok) {
                throw new Error('入出庫履歴の取得に失敗しました');
            }

            this.movements = await response.json();
            this.renderMovements();
            this.showToast('入出庫履歴を更新しました', 'success');
        } catch (error) {
            console.error('Error loading movements:', error);
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    // 入出庫履歴表示
    renderMovements() {
        const container = document.getElementById('movementsContainer');
        if (!container) return;

        if (this.movements.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12 text-gray-500">
                    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                    <p class="text-lg mt-4">入出庫履歴がありません</p>
                    <p class="text-sm mt-2">材料の入出庫を開始してください</p>
                </div>
            `;
            return;
        }

        const html = this.movements.map(movement => this.renderMovementCard(movement)).join('');
        container.innerHTML = html;
    }

    // 入出庫履歴カード描画
    renderMovementCard(movement) {
        const movementTypeText = movement.movement_type === 'in' ? '入庫' : '出庫';
        const movementTypeColor = movement.movement_type === 'in' ? 'text-green-600 bg-green-50' : 'text-red-600 bg-red-50';
        const borderColor = movement.movement_type === 'in' ? 'border-green-500' : 'border-red-500';

        const processedDate = new Date(movement.processed_at);

        return `
            <div class="bg-white rounded-lg shadow-md p-6 border-l-4 ${borderColor}">
                <div class="flex justify-between items-start mb-4">
                    <div class="flex-1">
                        <div class="flex items-center mb-2">
                            <span class="inline-block px-3 py-1 text-sm font-semibold rounded-full ${movementTypeColor}">
                                ${movementTypeText}
                            </span>
                            <span class="ml-3 text-lg font-bold">${movement.quantity}本</span>
                            ${movement.weight_kg !== undefined && movement.weight_kg !== null ? `<span class="ml-3 text-sm text-gray-600">${Number(movement.weight_kg).toFixed(3)}kg</span>` : ''}
                        </div>
                        <h3 class="text-lg font-semibold text-gray-800">${movement.material_name}</h3>
                        <p class="text-sm text-gray-600">ロット: ${movement.lot_number}</p>
                        <p class="text-sm text-gray-600">管理コード: ${movement.item_management_code}</p>
                    </div>
                    <div class="text-right text-sm text-gray-500">
                        <div>${processedDate.toLocaleDateString('ja-JP')}</div>
                        <div>${processedDate.toLocaleTimeString('ja-JP', {hour: '2-digit', minute: '2-digit'})}</div>
                    </div>
                </div>

                ${movement.instruction_number ? `
                    <div class="mb-3 p-3 bg-blue-50 rounded">
                        <span class="text-sm font-medium text-blue-800">指示書番号:</span>
                        <span class="text-sm text-blue-600 ml-2">${movement.instruction_number}</span>
                    </div>
                ` : ''}

                <div class="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <span class="text-gray-600">残在庫:</span>
                        <span class="font-medium">${movement.remaining_quantity}本</span>
                    </div>
                    <div>
                        <span class="text-gray-600">処理時刻:</span>
                        <span class="font-medium">${processedDate.toLocaleTimeString('ja-JP')}</span>
                    </div>
                </div>

                ${movement.notes ? `
                    <div class="mt-3 pt-3 border-t border-gray-200">
                        <p class="text-sm text-gray-600">${movement.notes}</p>
                    </div>
                ` : ''}
            </div>
        `;
    }

    // 管理コードで検索
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
            this.selectedItem = item;
            this.showItemForMovement(item);
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // 入出庫開始（外部から呼び出し）
    initMovement(managementCode, type) {
        this.currentMovementType = type;
        this.searchByCodeAndStart(managementCode);
    }

    // 管理コードで検索して入出庫開始
    async searchByCodeAndStart(managementCode) {
        try {
            const response = await fetch(`/api/inventory/search/${managementCode}`);
            if (!response.ok) {
                throw new Error('アイテムが見つかりません');
            }

            const item = await response.json();
            this.selectedItem = item;
            this.showMovementForm(item, this.currentMovementType);
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // アイテム選択後の入出庫フォーム表示
    showItemForMovement(item) {
        this.selectedItem = item;
        this.populateItemInfo(item);
        this.showModal('itemSelectModal');
    }

    // アイテム情報表示
    populateItemInfo(item) {
        const shapeNames = {
            'round': '丸棒',
            'hexagon': '六角棒',
            'square': '角棒'
        };

        document.getElementById('selectedMaterialName').textContent = item.material.name;
        document.getElementById('selectedShape').textContent = shapeNames[item.material.shape] || item.material.shape;
        document.getElementById('selectedDiameter').textContent = `${item.material.diameter_mm}mm`;
        document.getElementById('selectedLength').textContent = `${item.lot.length_mm}mm`;
        document.getElementById('selectedLotNumber').textContent = item.lot.lot_number;
        document.getElementById('selectedCurrentQuantity').textContent = `${item.item.current_quantity}本`;
        document.getElementById('selectedWeightPerPiece').textContent = `${item.weight_per_piece_kg}kg`;
        document.getElementById('selectedTotalWeight').textContent = `${item.total_weight_kg}kg`;
        document.getElementById('selectedLocation').textContent = item.location ? item.location.name : '未配置';
    }

    // 入出庫タイプ選択表示
    showMovementTypeSelection(type) {
        // 変更: 入庫は受入れページへ誘導（Movementsでは出庫のみ）
        if (type === 'in') {
            this.showToast('入庫は「入庫確認」ページで実施します', 'info');
            window.location.href = '/receiving';
            return;
        }

        if (!this.selectedItem) {
            this.showToast('先に材料を選択してください', 'error');
            return;
        }

        this.currentMovementType = type;
        this.showMovementForm(this.selectedItem, type);
    }

    // 入出庫フォーム表示
    showMovementForm(item, type) {
        this.selectedItem = item;
        this.currentMovementType = type;

        // フォームタイトル更新
        const modalTitle = document.getElementById('movementModalTitle');
        const typeText = type === 'in' ? '入庫' : '出庫';
        if (modalTitle) {
            modalTitle.textContent = `${typeText}処理`;
        }

        // フォーム初期化
        const form = document.getElementById('movementForm');
        if (form) {
            form.reset();
        }

        // 指示書番号フィールドの表示制御
        const instructionField = document.getElementById('instructionNumberField');
        if (instructionField) {
            if (type === 'out') {
                instructionField.classList.remove('hidden');
                document.getElementById('instructionNumber').required = true;
            } else {
                instructionField.classList.add('hidden');
                document.getElementById('instructionNumber').required = false;
            }
        }

        // 最大値設定（出庫の場合）
        const quantityInput = document.getElementById('movementQuantity');
        if (quantityInput && type === 'out') {
            quantityInput.max = item.item.current_quantity;
            quantityInput.placeholder = `最大 ${item.item.current_quantity}本`;
        }

        // 材料情報表示
        this.populateItemInfo(item);

        this.showModal('movementModal');
    }

    // 重量から本数計算
    calculateFromWeight() {
        if (!this.selectedItem) return;

        const weightInput = document.getElementById('movementWeight');
        const quantityInput = document.getElementById('movementQuantity');

        const weight = parseFloat(weightInput.value);
        if (weight && weight > 0) {
            const quantity = Math.floor(weight / this.selectedItem.weight_per_piece_kg);
            quantityInput.value = quantity;
        }
    }

    // 本数から重量計算
    calculateFromQuantity() {
        if (!this.selectedItem) return;

        const quantityInput = document.getElementById('movementQuantity');
        const weightInput = document.getElementById('movementWeight');

        const quantity = parseInt(quantityInput.value);
        if (quantity && quantity > 0) {
            const weight = (quantity * this.selectedItem.weight_per_piece_kg).toFixed(3);
            weightInput.value = weight;
        }
    }

    // 入出庫実行
    async submitMovement() {
        if (!this.selectedItem || !this.currentMovementType) {
            this.showToast('材料または処理タイプが選択されていません', 'error');
            return;
        }

        const formData = new FormData(document.getElementById('movementForm'));
        const data = Object.fromEntries(formData.entries());

        const quantityRaw = typeof data.quantity === 'string' ? data.quantity.trim() : '';
        const weightRaw = typeof data.weight_kg === 'string' ? data.weight_kg.trim() : (typeof data.weight === 'string' ? data.weight.trim() : '');

        const quantity = quantityRaw ? parseInt(quantityRaw, 10) : null;
        const weight = weightRaw ? parseFloat(weightRaw) : null;

        if ((!quantity || Number.isNaN(quantity) || quantity <= 0) && (!weight || Number.isNaN(weight) || weight <= 0)) {
            this.showToast('数量または重量を入力してください', 'error');
            return;
        }

        let resolvedQuantity = quantity;
        const weightPerPiece = this.selectedItem.weight_per_piece_kg;

        if ((!resolvedQuantity || Number.isNaN(resolvedQuantity) || resolvedQuantity <= 0) && weight && !Number.isNaN(weight) && weight > 0 && weightPerPiece) {
            resolvedQuantity = Math.max(1, Math.round(weight / weightPerPiece));
        }

        if (!resolvedQuantity || Number.isNaN(resolvedQuantity) || resolvedQuantity <= 0) {
            this.showToast('数量換算に失敗しました。入力内容を確認してください', 'error');
            return;
        }

        // 出庫時の在庫チェック
        if (this.currentMovementType === 'out' && resolvedQuantity > this.selectedItem.item.current_quantity) {
            this.showToast(`在庫が不足しています。現在庫: ${this.selectedItem.item.current_quantity}本`, 'error');
            return;
        }

        // 出庫時の指示書番号チェック
        if (this.currentMovementType === 'out' && !data.instruction_number) {
            this.showToast('出庫時は指示書番号が必須です', 'error');
            return;
        }

        try {
            const submitBtn = document.querySelector('#movementForm button[type="submit"]');
            this.setLoading(submitBtn, true);

            const endpoint = `/api/movements/${this.currentMovementType}/${this.selectedItem.item.id}`;
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    quantity: quantity && quantity > 0 ? quantity : resolvedQuantity,
                    weight_kg: weight && weight > 0 ? weight : undefined,
                    instruction_number: data.instruction_number || null,
                    notes: data.notes || null
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '処理に失敗しました');
            }

            const result = await response.json();
            const typeText = this.currentMovementType === 'in' ? '入庫' : '出庫';

            const weightInfo = result.calculated_weight_kg ? ` / ${result.calculated_weight_kg}kg` : '';
            this.showToast(`${typeText}処理が完了しました (${result.old_quantity}本 → ${result.new_quantity}本${weightInfo})`, 'success');
            this.closeModal();
            this.loadMovements();

            // 在庫一覧の更新（他の画面からの呼び出しの場合）
            if (window.inventoryManager) {
                window.inventoryManager.loadInventory();
            }

        } catch (error) {
            this.showToast(error.message, 'error');
        } finally {
            const submitBtn = document.querySelector('#movementForm button[type="submit"]');
            this.setLoading(submitBtn, false);
        }
    }

    // 指示書番号で検索
    async searchByInstruction() {
        const instructionInput = document.getElementById('instructionNumberSearch');
        const instructionNumber = instructionInput?.value?.trim();

        if (!instructionNumber) {
            this.showToast('指示書番号を入力してください', 'error');
            return;
        }

        try {
            const response = await fetch(`/api/movements/by-instruction/${instructionNumber}`);
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('指定された指示書番号の履歴が見つかりません');
                }
                throw new Error('検索に失敗しました');
            }

            const data = await response.json();
            this.showInstructionResult(data);
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // 指示書検索結果表示
    showInstructionResult(data) {
        const container = document.getElementById('instructionResultContainer');
        if (!container) return;

        const html = `
            <div class="mb-4 p-4 bg-blue-50 rounded-lg">
                <h4 class="font-semibold text-blue-800">指示書番号: ${data.instruction_number}</h4>
                <p class="text-sm text-blue-600">総移動件数: ${data.total_movements}件</p>
            </div>
            <div class="space-y-4">
                ${data.movements.map(movement => `
                    <div class="border rounded-lg p-4">
                        <div class="flex justify-between items-start mb-2">
                            <div>
                                <span class="inline-block px-2 py-1 text-xs font-semibold rounded ${
                                    movement.movement_type === 'in' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                                }">
                                    ${movement.movement_type === 'in' ? '入庫' : '出庫'}
                                </span>
                                <span class="ml-2 font-semibold">${movement.quantity}本</span>
                                <span class="ml-2 text-gray-600">${movement.weight_kg}kg</span>
                            </div>
                            <div class="text-sm text-gray-500">
                                ${new Date(movement.processed_at).toLocaleString('ja-JP')}
                            </div>
                        </div>
                        <div class="text-sm">
                            <div class="font-medium">${movement.material.name}</div>
                            <div class="text-gray-600">ロット: ${movement.lot.lot_number}</div>
                            <div class="text-gray-600">管理コード: ${movement.item.management_code}</div>
                        </div>
                        ${movement.notes ? `<div class="mt-2 text-sm text-gray-600">${movement.notes}</div>` : ''}
                    </div>
                `).join('')}
            </div>
        `;

        container.innerHTML = html;
        this.showModal('instructionResultModal');
    }

    // 検索実行
    async searchMovements() {
        const formData = new FormData(document.getElementById('movementSearchForm'));
        const filters = Object.fromEntries(formData.entries());

        // 空の値を除外
        Object.keys(filters).forEach(key => {
            if (filters[key] === '') {
                delete filters[key];
            }
        });

        await this.loadMovements(filters);
    }

    // 検索デバウンス
    debounceSearch() {
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.searchMovements();
        }, 300);
    }

    // QRスキャン開始
    startQRScan() {
        if (window.qrScanner) {
            window.qrScanner.startScan((code) => {
                const codeInput = document.getElementById('managementCodeInput');
                if (codeInput) {
                    codeInput.value = code;
                }
                this.searchByCode();
            });
        } else {
            this.showToast('QRスキャナーが利用できません', 'error');
        }
    }

    // ローディング状態設定
    setLoading(button, loading) {
        if (!button) return;

        if (loading) {
            button.disabled = true;
            button.innerHTML = `
                <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                処理中...
            `;
        } else {
            button.disabled = false;
            button.innerHTML = this.currentMovementType === 'in' ? '入庫実行' : '出庫実行';
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

        // フォームリセット
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            if (form.id !== 'movementSearchForm') {
                form.reset();
            }
        });

        this.selectedItem = null;
        this.currentMovementType = null;
    }

    // ローディング表示
    showLoading() {
        const loader = document.getElementById('movementLoading');
        if (loader) {
            loader.classList.remove('hidden');
        }
    }

    // ローディング非表示
    hideLoading() {
        const loader = document.getElementById('movementLoading');
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
let movementManager;

// DOM読み込み完了後に初期化
document.addEventListener('DOMContentLoaded', () => {
    movementManager = new MovementManager();
});
