// 材料管理JavaScript機能

class MaterialManager {
    constructor() {
        this.materials = [];
        this.editingMaterial = null;
        this.init();
    }

    init() {
        this.loadMaterials();
        this.bindEvents();
        this.initForms();
        this.setupModals();
    }

    // イベントバインディング
    bindEvents() {
        // 新規登録ボタン
        const addBtn = document.getElementById('addMaterialBtn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.showCreateForm());
        }

        // 検索フォーム
        const searchForm = document.getElementById('searchForm');
        if (searchForm) {
            searchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.searchMaterials();
            });
        }

        // 検索条件リアルタイム更新
        const searchInputs = document.querySelectorAll('#searchForm input, #searchForm select');
        searchInputs.forEach(input => {
            input.addEventListener('input', () => this.debounceSearch());
        });

        // フォーム送信
        const createForm = document.getElementById('createMaterialForm');
        if (createForm) {
            createForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitMaterial();
            });
        }

        // 重量計算ボタン
        const calcBtn = document.getElementById('calculateWeightBtn');
        if (calcBtn) {
            calcBtn.addEventListener('click', () => this.calculateWeight());
        }

        // 形状変更時の処理
        const shapeSelect = document.getElementById('shape');
        if (shapeSelect) {
            shapeSelect.addEventListener('change', () => this.updateShapeLabel());
        }

        // モーダル閉じる処理
        const closeButtons = document.querySelectorAll('[data-dismiss="modal"]');
        closeButtons.forEach(btn => {
            btn.addEventListener('click', () => this.closeModal());
        });
    }

    // モーダル共通処理設定
    setupModals() {
        Utils.modal.setupEventListeners(['materialModal', 'weightCalculatorModal']);
    }

    // フォーム初期化
    initForms() {
        this.updateShapeLabel();
        this.resetForms();
    }

    // 材料一覧読み込み
    async loadMaterials(filters = {}) {
        try {
            this.showLoading();
            const params = new URLSearchParams();

            Object.keys(filters).forEach(key => {
                if (filters[key] !== null && filters[key] !== '') {
                    params.append(key, filters[key]);
                }
            });

            const response = await fetch(`/api/materials?${params}`);
            if (!response.ok) {
                throw new Error('材料データの取得に失敗しました');
            }

            this.materials = await response.json();
            this.renderMaterialsList();
            this.showToast('材料一覧を更新しました', 'success');
        } catch (error) {
            console.error('Error loading materials:', error);
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    // 材料リスト表示
    renderMaterialsList() {
        const container = document.getElementById('materialsContainer');
        if (!container) return;

        if (this.materials.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-500">
                    <p class="text-lg">登録された材料がありません</p>
                    <button onclick="materialManager.showCreateForm()"
                            class="mt-4 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">
                        最初の材料を登録
                    </button>
                </div>
            `;
            return;
        }

        const html = this.materials.map(material => this.renderMaterialCard(material)).join('');
        container.innerHTML = html;
    }

    // 材料カード描画
    renderMaterialCard(material) {
        const shapeNames = {
            'round': '丸棒',
            'hexagon': '六角棒',
            'square': '角棒'
        };

        return `
            <div class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h3 class="text-lg font-semibold text-gray-800">${material.name}</h3>
                        <p class="text-sm text-gray-600">${material.description || '説明なし'}</p>
                    </div>
                    <div class="flex space-x-2">
                        <button onclick="materialManager.editMaterial(${material.id})"
                                class="text-blue-600 hover:text-blue-800">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                      d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                            </svg>
                        </button>
                        <button onclick="materialManager.deleteMaterial(${material.id})"
                                class="text-red-600 hover:text-red-800">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                            </svg>
                        </button>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <span class="text-gray-600">形状:</span>
                        <span class="font-medium">${shapeNames[material.shape] || material.shape}</span>
                    </div>
                    <div>
                        <span class="text-gray-600">寸法:</span>
                        <span class="font-medium">${material.diameter_mm}mm</span>
                    </div>
                    <div>
                        <span class="text-gray-600">比重:</span>
                        <span class="font-medium">${material.current_density} g/cm³</span>
                    </div>
                    <div>
                        <span class="text-gray-600">状態:</span>
                        <span class="inline-block px-2 py-1 text-xs rounded-full ${material.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                            ${material.is_active ? '有効' : '無効'}
                        </span>
                    </div>
                </div>

                <div class="mt-4 pt-4 border-t border-gray-200">
                    <button onclick="materialManager.showWeightCalculator(${material.id})"
                            class="w-full bg-gray-100 text-gray-700 py-2 px-4 rounded hover:bg-gray-200 transition-colors">
                        重量計算
                    </button>
                </div>
            </div>
        `;
    }

    // 新規作成フォーム表示
    showCreateForm() {
        this.editingMaterial = null;
        this.resetForms();
        document.getElementById('modalTitle').textContent = '新しい材料を登録';
        document.getElementById('submitBtn').textContent = '登録';
        Utils.modal.open('materialModal');
    }

    // 編集フォーム表示
    async editMaterial(materialId) {
        try {
            const response = await fetch(`/api/materials/${materialId}`);
            if (!response.ok) {
                throw new Error('材料データの取得に失敗しました');
            }

            this.editingMaterial = await response.json();
            this.populateEditForm(this.editingMaterial);
            document.getElementById('modalTitle').textContent = '材料を編集';
            document.getElementById('submitBtn').textContent = '更新';
            Utils.modal.open('materialModal');
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // 編集フォームにデータ設定
    populateEditForm(material) {
        document.getElementById('name').value = material.name;
        document.getElementById('description').value = material.description || '';
        document.getElementById('shape').value = material.shape;
        document.getElementById('diameter_mm').value = material.diameter_mm;
        document.getElementById('current_density').value = material.current_density;
        this.updateShapeLabel();
    }

    // 材料削除
    async deleteMaterial(materialId) {
        if (!confirm('この材料を削除してもよろしいですか？')) {
            return;
        }

        try {
            const response = await fetch(`/api/materials/${materialId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error('材料の削除に失敗しました');
            }

            this.showToast('材料を削除しました', 'success');
            this.loadMaterials();
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // 材料データ送信
    async submitMaterial() {
        const formData = new FormData(document.getElementById('createMaterialForm'));
        const data = Object.fromEntries(formData.entries());

        // 数値フィールド変換
        data.diameter_mm = parseFloat(data.diameter_mm);
        data.current_density = parseFloat(data.current_density);

        try {
            const url = this.editingMaterial
                ? `/api/materials/${this.editingMaterial.id}`
                : '/api/materials';

            const method = this.editingMaterial ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '登録に失敗しました');
            }

            const result = await response.json();
            this.showToast(
                this.editingMaterial ? '材料を更新しました' : '材料を登録しました',
                'success'
            );
            Utils.modal.close('materialModal');
            this.loadMaterials();
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // 検索実行
    async searchMaterials() {
        const formData = new FormData(document.getElementById('searchForm'));
        const filters = Object.fromEntries(formData.entries());

        // 空の値を除外
        Object.keys(filters).forEach(key => {
            if (filters[key] === '') {
                delete filters[key];
            }
        });

        await this.loadMaterials(filters);
    }

    // 検索デバウンス
    debounceSearch() {
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.searchMaterials();
        }, 300);
    }

    // 重量計算表示
    async showWeightCalculator(materialId) {
        const material = this.materials.find(m => m.id === materialId);
        if (!material) return;

        document.getElementById('calcMaterialName').textContent = material.name;
        document.getElementById('calcMaterialId').value = materialId;
        document.getElementById('calcLength').value = '';
        document.getElementById('calcQuantity').value = '1';
        document.getElementById('calcResult').innerHTML = '';

        Utils.modal.open('weightCalculatorModal');
    }

    // 重量計算実行
    async calculateWeight() {
        const materialId = document.getElementById('calcMaterialId').value;
        const length = parseFloat(document.getElementById('calcLength').value);
        const quantity = parseInt(document.getElementById('calcQuantity').value);

        if (!length || length <= 0) {
            this.showToast('長さを正しく入力してください', 'error');
            return;
        }

        if (!quantity || quantity <= 0) {
            this.showToast('本数を正しく入力してください', 'error');
            return;
        }

        try {
            const response = await fetch(`/api/materials/${materialId}/calculate-weight?length_mm=${length}&quantity=${quantity}`);
            if (!response.ok) {
                throw new Error('重量計算に失敗しました');
            }

            const result = await response.json();
            this.displayCalculationResult(result);
        } catch (error) {
            this.showToast(error.message, 'error');
        }
    }

    // 計算結果表示
    displayCalculationResult(result) {
        const html = `
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-4">
                <h4 class="font-semibold text-blue-800 mb-3">計算結果</h4>
                <div class="grid grid-cols-2 gap-3 text-sm">
                    <div>
                        <span class="text-gray-600">体積（1本）:</span>
                        <span class="font-medium">${result.volume_per_piece_cm3} cm³</span>
                    </div>
                    <div>
                        <span class="text-gray-600">重量（1本）:</span>
                        <span class="font-medium">${result.weight_per_piece_kg} kg</span>
                    </div>
                    <div class="col-span-2 pt-2 border-t border-blue-200">
                        <span class="text-gray-600">総重量（${result.quantity}本）:</span>
                        <span class="font-bold text-blue-800 text-lg">${result.total_weight_kg} kg</span>
                    </div>
                </div>
            </div>
        `;
        document.getElementById('calcResult').innerHTML = html;
    }

    // 形状ラベル更新
    updateShapeLabel() {
        const shape = document.getElementById('shape').value;
        const label = document.getElementById('diameterLabel');

        if (label) {
            switch (shape) {
                case 'round':
                    label.textContent = '直径 (mm)';
                    break;
                case 'hexagon':
                    label.textContent = '対辺距離 (mm)';
                    break;
                case 'square':
                    label.textContent = '一辺の長さ (mm)';
                    break;
                default:
                    label.textContent = '寸法 (mm)';
            }
        }
    }

    // フォームリセット
    resetForms() {
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            if (form.id !== 'searchForm') {
                form.reset();
            }
        });
        this.updateShapeLabel();
    }

    // モーダル表示
    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        }
    }

    // モーダル非表示（レガシー対応）
    closeModal() {
        Utils.modal.close('materialModal');
        Utils.modal.close('weightCalculatorModal');
    }

    // ローディング表示
    showLoading() {
        const loader = document.getElementById('loading');
        if (loader) {
            loader.classList.remove('hidden');
        }
    }

    // ローディング非表示
    hideLoading() {
        const loader = document.getElementById('loading');
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
let materialManager;

// DOM読み込み完了後に初期化
document.addEventListener('DOMContentLoaded', () => {
    materialManager = new MaterialManager();
});