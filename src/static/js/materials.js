// 材料管理JavaScript機能

class MaterialManager {
  constructor() {
    this.materials = [];
    this.editingMaterial = null;
    this.currentPage = 1;
    this.itemsPerPage = 100;
    this.totalItems = 0;
    this.totalPages = 0;
    this.currentFilters = {};
    this.init();
  }

  init() {
    this.loadMaterials();
    this.loadDensityPresets();
    this.bindEvents();
    this.initForms();
    this.setupModals();
  }

  // イベントバインディング
  bindEvents() {

    // 新規登録ボタン
    const addBtn = document.getElementById("addMaterialBtn");
    if (addBtn) {
      addBtn.addEventListener("click", () => this.showCreateForm());
    }

    // 検索フォーム
    const searchForm = document.getElementById("searchForm");
    if (searchForm) {
      searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.searchMaterials();
      });
    }

    // 検索条件リアルタイム更新
    const searchInputs = document.querySelectorAll(
      "#searchForm input, #searchForm select"
    );
    searchInputs.forEach((input) => {
      input.addEventListener("input", () => this.debounceSearch());
    });

    // リセットボタン
    const resetBtn = document.querySelector('button[type="reset"]');
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        setTimeout(() => this.searchMaterials(), 100);
      });
    }

    // フォーム送信
    const createForm = document.getElementById("createMaterialForm");
    if (createForm) {
      createForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.submitMaterial();
      });
    }

    // 重量計算ボタン
    const calcBtn = document.getElementById("calculateWeightBtn");
    if (calcBtn) {
      calcBtn.addEventListener("click", () => this.calculateWeight());
    }

    // 形状変更時の処理
    const shapeSelect = document.getElementById("shape");
    if (shapeSelect) {
      shapeSelect.addEventListener("change", () => this.updateShapeLabel());
    }

    // モーダル閉じる処理
    const closeButtons = document.querySelectorAll('[data-dismiss="modal"]');
    closeButtons.forEach((btn) => {
      btn.addEventListener("click", () => this.closeModal());
    });

    // 比重プリセット選択時の処理
    const densityPresetSelect = document.getElementById(
      "density_preset_select"
    );
    if (densityPresetSelect) {
      densityPresetSelect.addEventListener("change", (e) =>
        this.onDensityPresetChange(e)
      );
    }

    // ページネーション関連のイベント
    const prevPage = document.getElementById("prevPage");
    const nextPage = document.getElementById("nextPage");
    const prevPageMobile = document.getElementById("prevPageMobile");
    const nextPageMobile = document.getElementById("nextPageMobile");

    // 上部ページネーション要素
    const prevPageTop = document.getElementById("prevPageTop");
    const nextPageTop = document.getElementById("nextPageTop");
    const prevPageMobileTop = document.getElementById("prevPageMobileTop");
    const nextPageMobileTop = document.getElementById("nextPageMobileTop");

    if (prevPage) {
      prevPage.addEventListener("click", (e) => {
        e.preventDefault();
        this.goToPage(this.currentPage - 1);
      });
    }
    if (nextPage) {
      nextPage.addEventListener("click", (e) => {
        e.preventDefault();
        this.goToPage(this.currentPage + 1);
      });
    }
    if (prevPageMobile) {
      prevPageMobile.addEventListener("click", (e) => {
        e.preventDefault();
        this.goToPage(this.currentPage - 1);
      });
    }
    if (nextPageMobile) {
      nextPageMobile.addEventListener("click", (e) => {
        e.preventDefault();
        this.goToPage(this.currentPage + 1);
      });
    }

    // 上部ページネーションイベントバインディング
    if (prevPageTop) {
      prevPageTop.addEventListener("click", (e) => {
        e.preventDefault();
        this.goToPage(this.currentPage - 1);
      });
    }
    if (nextPageTop) {
      nextPageTop.addEventListener("click", (e) => {
        e.preventDefault();
        this.goToPage(this.currentPage + 1);
      });
    }
    if (prevPageMobileTop) {
      prevPageMobileTop.addEventListener("click", (e) => {
        e.preventDefault();
        this.goToPage(this.currentPage - 1);
      });
    }
    if (nextPageMobileTop) {
      nextPageMobileTop.addEventListener("click", (e) => {
        e.preventDefault();
        this.goToPage(this.currentPage + 1);
      });
    }
  }

  // モーダル共通処理設定
  setupModals() {
    Utils.modal.setupEventListeners([
      "materialModal",
      "weightCalculatorModal",
    ]);
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

      // ページネーション設定
      params.append(
        "skip",
        ((this.currentPage - 1) * this.itemsPerPage).toString()
      );
      params.append("limit", this.itemsPerPage.toString());

      // フィルター設定
      Object.keys(filters).forEach((key) => {
        if (filters[key] !== null && filters[key] !== "") {
          params.append(key, filters[key]);
        }
      });

      this.currentFilters = filters;

      // 材料データと総件数を並行取得
      const [materialsResponse, countResponse] = await Promise.all([
        fetch(`/api/materials/?${params}`),
        fetch(`/api/materials/count?${new URLSearchParams(filters)}`),
      ]);

      if (!materialsResponse.ok || !countResponse.ok) {
        throw new Error("材料データの取得に失敗しました");
      }

      this.materials = await materialsResponse.json();
      const countData = await countResponse.json();
      this.totalItems = countData.total || 0;
      this.totalPages = Math.ceil(this.totalItems / this.itemsPerPage) || 1;

      console.log(
        `材料データ取得完了: ${this.materials.length}件 (総件数: ${this.totalItems}件)`
      );
      this.renderMaterialsList();
      this.updatePagination();

      if (this.currentPage === 1) {
        this.showToast(
          `材料一覧を更新しました (総件数: ${this.totalItems}件)`,
          "success"
        );
      }
    } catch (error) {
      console.error("Error loading materials:", error);
      this.showToast(error.message, "error");
    } finally {
      this.hideLoading();
    }
  }

  // 材料リスト表示
  renderMaterialsList() {
    const tbody = document.getElementById("materialsTableBody");
    if (!tbody) return;

    if (this.materials.length === 0) {
      tbody.innerHTML = `
                <tr>
                    <td colspan="4" class="px-6 py-16 text-center">
                        <div class="inline-flex flex-col items-center">
                            <div class="p-6 bg-neutral-100 rounded-full mb-6">
                                <i class="fas fa-box-open text-5xl text-neutral-400"></i>
                            </div>
                            <p class="text-xl font-semibold text-neutral-700 mb-3">登録された材料がありません</p>
                            <p class="text-sm text-neutral-500 mb-6">最初の材料を登録してください</p>
                            <button onclick="materialManager.showCreateForm()"
                                    class="bg-primary-blue text-white font-semibold py-2 px-6 rounded-lg hover:bg-opacity-90">
                                <i class="fas fa-plus mr-2"></i>最初の材料を登録
                            </button>
                        </div>
                    </td>
                </tr>
            `;
      return;
    }

    const html = this.materials
      .map((material) => this.renderMaterialRow(material))
      .join("");
    tbody.innerHTML = html;
  }

  // 材料カード描画（現在は未使用）
  renderMaterialCard(material) {
    const shapeNames = {
      round: "丸棒",
      hexagon: "六角棒",
      square: "角棒",
    };

    return `
            <div class="bg-white rounded-lg border border-neutral-200 shadow-sm p-6 hover:shadow-md transition-shadow">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h3 class="text-lg font-semibold text-neutral-800">${
                          material.display_name || material.name
                        }</h3>
                        <p class="text-sm text-neutral-600">${
                          material.description || "説明なし"
                        }</p>
                    </div>
                    <div class="flex space-x-2">
                        <button onclick="materialManager.editMaterial(${
                          material.id
                        })"
                                class="text-primary-blue hover:text-primary-blue">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                      d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                            </svg>
                        </button>
                        <button onclick="materialManager.deleteMaterial(${
                          material.id
                        })"
                                class="text-danger-red hover:text-danger-red">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                            </svg>
                        </button>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <span class="text-neutral-600">形状:</span>
                        <span class="font-medium text-neutral-800">${
                          shapeNames[material.shape] || material.shape
                        }</span>
                    </div>
                    <div>
                        <span class="text-neutral-600">寸法:</span>
                        <span class="font-medium text-neutral-800">${
                          material.diameter_mm
                        }mm</span>
                    </div>
                    <div>
                        <span class="text-neutral-600">比重:</span>
                        <span class="font-medium text-neutral-800">${
                          material.current_density
                        } g/cm³</span>
                    </div>
                    <div>
                        <span class="text-neutral-600">状態:</span>
                        <span class="inline-block px-2 py-1 text-xs rounded-full ${
                          material.is_active
                            ? "bg-success-green bg-opacity-10 text-success-green"
                            : "bg-danger-red bg-opacity-10 text-danger-red"
                        }">
                            ${material.is_active ? "有効" : "無効"}
                        </span>
                    </div>
                </div>

                <div class="mt-4 pt-4 border-t border-neutral-200">
                    <button onclick="materialManager.showWeightCalculator(${
                      material.id
                    })"
                            class="w-full bg-neutral-100 text-neutral-700 py-2 px-4 rounded-lg hover:bg-neutral-200 transition-colors">
                        重量計算
                    </button>
                </div>
            </div>
        `;
  }

  // 材料行描画（テーブル用）
  renderMaterialRow(material) {
    const shapeNames = {
      round: "丸棒",
      hexagon: "六角棒",
      square: "角棒",
    };

    // 材料仕様名（display_nameを表示）
    const materialSpec = material.display_name || "（未設定）";

    // 形状表示
    const shapeText = shapeNames[material.shape] || material.shape || "（未設定）";

    // 形状アイコン
    const shapeIcons = {
      round: '<i class="fas fa-circle text-blue-500 mr-2"></i>',
      hexagon: '<i class="fas fa-hexagon text-green-500 mr-2"></i>',
      square: '<i class="fas fa-square text-purple-500 mr-2"></i>',
    };
    const shapeIcon = shapeIcons[material.shape] || '<i class="fas fa-shapes text-gray-500 mr-2"></i>';

    return `
            <tr class="table-row-hover">
                <td class="px-4 py-3">
                    <div class="text-sm font-semibold text-neutral-900">${materialSpec}</div>
                </td>
                <td class="px-4 py-3">
                    <div class="text-sm font-medium text-neutral-700 flex items-center">
                        ${shapeIcon}${shapeText}
                    </div>
                </td>
                <td class="px-4 py-3">
                    <div class="text-sm font-medium text-neutral-900">${material.diameter_mm}</div>
                </td>
                <td class="px-4 py-3 text-right">
                    <div class="flex justify-end space-x-2">
                        <button onclick="materialManager.editMaterial(${material.id})"
                                class="p-2 rounded-lg bg-primary-blue bg-opacity-10 text-primary-blue hover:bg-opacity-20 transition-colors"
                                title="編集">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button onclick="materialManager.deleteMaterial(${material.id})"
                                class="p-2 rounded-lg bg-danger-red bg-opacity-10 text-danger-red hover:bg-opacity-20 transition-colors"
                                title="削除">
                            <i class="fas fa-trash"></i>
                        </button>
                        <button onclick="materialManager.showWeightCalculator(${material.id})"
                                class="p-2 rounded-lg bg-success-green bg-opacity-10 text-success-green hover:bg-opacity-20 transition-colors"
                                title="重量計算">
                            <i class="fas fa-calculator"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
  }

  // 新規作成フォーム表示
  showCreateForm() {
    this.editingMaterial = null;
    this.resetForms();
    document.getElementById("modalTitle").textContent = "新しい材料を登録";
    document.getElementById("submitBtn").textContent = "登録";
    Utils.modal.open("materialModal");
  }

  // 編集フォーム表示
  async editMaterial(materialId) {
    try {
      const response = await fetch(`/api/materials/${materialId}`);
      if (!response.ok) {
        throw new Error("材料データの取得に失敗しました");
      }

      this.editingMaterial = await response.json();
      // 変更検知用の元値を保持
      this._editingOriginal = {
        display_name: this.editingMaterial.display_name,
        shape: this.editingMaterial.shape,
        diameter_mm: this.editingMaterial.diameter_mm,
        current_density: this.editingMaterial.current_density,
      };
      this.populateEditForm(this.editingMaterial);
      document.getElementById("modalTitle").textContent = "材料を編集";
      document.getElementById("submitBtn").textContent = "更新";
      Utils.modal.open("materialModal");
    } catch (error) {
      this.showToast(error.message, "error");
    }
  }

  // 編集フォームにデータ設定
  populateEditForm(material) {
    document.getElementById("display_name").value = material.display_name || "";
    document.getElementById("shape").value = material.shape;
    document.getElementById("diameter_mm").value = material.diameter_mm;
    document.getElementById("current_density").value = material.current_density;

    this.updateShapeLabel();
  }

  // 材料削除
  async deleteMaterial(materialId) {
    if (!confirm("この材料を削除してもよろしいですか？")) {
      return;
    }

    try {
      const response = await fetch(`/api/materials/${materialId}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error("材料の削除に失敗しました");
      }

      this.showToast("材料を削除しました", "success");
      this.loadMaterials();
    } catch (error) {
      this.showToast(error.message, "error");
    }
  }

  // 材料データ送信
  async submitMaterial() {
    const formData = new FormData(
      document.getElementById("createMaterialForm")
    );
    const data = Object.fromEntries(formData.entries());

    // 説明フィールドが空の場合は適切に処理
    if (data.description === "" || !data.description) {
      data.description = null;
    }

    // 数値フィールド変換
    data.diameter_mm = parseFloat(data.diameter_mm);
    data.current_density = parseFloat(data.current_density);

    try {
      const url = this.editingMaterial
        ? `/api/materials/${this.editingMaterial.id}`
        : "/api/materials";

      const method = this.editingMaterial ? "PUT" : "POST";

      // 重要項目変更時の警告確認（編集時のみ）
      if (this.editingMaterial && this._editingOriginal) {
        const changes = [];
        const shapeOld = this._editingOriginal.shape;
        const shapeNew = document.getElementById("shape").value;
        if (String(shapeOld) !== String(shapeNew)) {
          changes.push(`・形状: ${shapeOld} → ${shapeNew}`);
        }
        const diaOld = Number(this._editingOriginal.diameter_mm);
        const diaNew = Number(data.diameter_mm);
        if (!Number.isNaN(diaNew) && diaOld !== diaNew) {
          changes.push(`・寸法(mm): ${diaOld} → ${diaNew}`);
        }
        const denOld = Number(this._editingOriginal.current_density);
        const denNew = Number(data.current_density);
        if (!Number.isNaN(denNew) && denOld !== denNew) {
          changes.push(`・比重(g/cm³): ${denOld} → ${denNew}`);
        }

        if (changes.length > 0) {
          const msg =
            "この材料の寸法・形状・比重の変更は在庫の重量計算や集計に即時影響します。\n" +
            changes.join("\n") +
            "\n\n変更を続行しますか？";
          const ok = confirm(msg);
          if (!ok) {
            return; // ユーザーがキャンセル
          }
        }
      }

      const response = await fetch(url, {
        method: method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "登録に失敗しました");
      }

      const result = await response.json();
      this.showToast(
        this.editingMaterial ? "材料を更新しました" : "材料を登録しました",
        "success"
      );
      Utils.modal.close("materialModal");
      this.loadMaterials();
    } catch (error) {
      this.showToast(error.message, "error");
    }
  }

  // 検索実行
  async searchMaterials() {
    const formData = new FormData(document.getElementById("searchForm"));
    const filters = Object.fromEntries(formData.entries());

    // 空の値を除外
    Object.keys(filters).forEach((key) => {
      if (filters[key] === "") {
        delete filters[key];
      }
    });

    // 検索時は1ページ目に戻る
    this.currentPage = 1;
    this.loadMaterials(filters);
  }

  // 検索条件をクリア
  clearSearch() {
    const searchForm = document.getElementById("searchForm");
    if (searchForm) {
      searchForm.reset();
      this.currentPage = 1;
      this.loadMaterials({});
    }
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
    const material = this.materials.find((m) => m.id === materialId);
    if (!material) return;

    document.getElementById("calcMaterialName").textContent = material.display_name || "（未設定）";
    document.getElementById("calcMaterialId").value = materialId;
    document.getElementById("calcLength").value = "";
    document.getElementById("calcQuantity").value = "1";
    document.getElementById("calcResult").innerHTML = "";

    Utils.modal.open("weightCalculatorModal");
  }

  // 重量計算実行
  async calculateWeight() {
    const materialId = document.getElementById("calcMaterialId").value;
    const length = parseFloat(document.getElementById("calcLength").value);
    const quantity = parseInt(document.getElementById("calcQuantity").value);

    if (!length || length <= 0) {
      this.showToast("長さを正しく入力してください", "error");
      return;
    }

    if (!quantity || quantity <= 0) {
      this.showToast("本数を正しく入力してください", "error");
      return;
    }

    try {
      const response = await fetch(
        `/api/materials/${materialId}/calculate-weight?length_mm=${length}&quantity=${quantity}`
      );
      if (!response.ok) {
        throw new Error("重量計算に失敗しました");
      }

      const result = await response.json();
      this.displayCalculationResult(result);
    } catch (error) {
      this.showToast(error.message, "error");
    }
  }

  // 計算結果表示
  displayCalculationResult(result) {
    const html = `
            <div>
                <div class="flex items-center mb-4">
                    <div class="p-2 bg-success-green bg-opacity-10 rounded-lg mr-3">
                        <i class="fas fa-check-circle text-success-green text-lg"></i>
                    </div>
                    <h4 class="text-lg font-semibold text-neutral-900">計算結果</h4>
                </div>
                <div class="space-y-4">
                    <div class="flex justify-between items-center p-4 bg-primary-blue bg-opacity-5 rounded-lg border border-primary-blue border-opacity-20">
                        <span class="text-sm font-medium text-neutral-700">体積（1本）</span>
                        <span class="text-base font-semibold text-primary-blue">${result.volume_per_piece_cm3} cm³</span>
                    </div>
                    <div class="flex justify-between items-center p-4 bg-success-green bg-opacity-5 rounded-lg border border-success-green border-opacity-20">
                        <span class="text-sm font-medium text-neutral-700">重量（1本）</span>
                        <span class="text-base font-semibold text-success-green">${result.weight_per_piece_kg} kg</span>
                    </div>
                    <div class="p-5 bg-primary-blue rounded-lg">
                        <div class="text-white text-center">
                            <div class="text-sm font-medium mb-2 opacity-90">総重量（${result.quantity}本）</div>
                            <div class="text-2xl font-semibold">${result.total_weight_kg} kg</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    document.getElementById("calcResult").innerHTML = html;
  }

  // 形状ラベル更新
  updateShapeLabel() {
    const shape = document.getElementById("shape").value;
    const label = document.getElementById("diameterLabel");

    if (label) {
      switch (shape) {
        case "round":
          label.textContent = "直径 (mm)";
          break;
        case "hexagon":
          label.textContent = "対辺距離 (mm)";
          break;
        case "square":
          label.textContent = "一辺の長さ (mm)";
          break;
        default:
          label.textContent = "寸法 (mm)";
      }
    }
  }

  // フォームリセット
  resetForms() {
    const forms = document.querySelectorAll("form");
    forms.forEach((form) => {
      if (form.id !== "searchForm") {
        form.reset();
      }
    });
    this.updateShapeLabel();
  }

  // モーダル表示
  showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove("hidden");
      modal.classList.add("flex");
    }
  }

  // モーダル非表示（レガシー対応）
  closeModal() {
    Utils.modal.close("materialModal");
    Utils.modal.close("weightCalculatorModal");
  }

  // ローディング表示
  showLoading() {
    const loader = document.getElementById("loading");
    if (loader) {
      loader.classList.remove("hidden");
    }
  }

  // ローディング非表示
  hideLoading() {
    const loader = document.getElementById("loading");
    if (loader) {
      loader.classList.add("hidden");
    }
  }

  // トースト通知（base.htmlのグローバル関数を使用）
  showToast(message, type = "info") {
    if (typeof window.showToast === 'function') {
      window.showToast(message, type);
    } else {
      console.log(`[${type.toUpperCase()}] ${message}`);
    }
  }

  // 比重プリセット読み込み
  async loadDensityPresets() {
    try {
      const response = await fetch("/api/density-presets/");
      if (!response.ok) {
        throw new Error("比重プリセットの取得に失敗しました");
      }

      const presets = await response.json();
      this.renderDensityPresets(presets);
    } catch (error) {
      console.error("Error loading density presets:", error);
      // エラーが発生してもアプリケーションの動作は継続
    }
  }

  // 比重プリセットをドロップダウンに表示
  renderDensityPresets(presets) {
    const select = document.getElementById("density_preset_select");
    if (!select) return;

    // 既存のオプションをクリア（最初のオプションは残す）
    while (select.children.length > 1) {
      select.removeChild(select.lastChild);
    }

    // プリセットオプションを追加
    presets.forEach((preset) => {
      const option = document.createElement("option");
      option.value = preset.density;
      option.textContent = `${preset.name} (${preset.density})`;
      if (preset.description) {
        option.title = preset.description;
      }
      select.appendChild(option);
    });
  }

  // 比重プリセット選択時の処理
  onDensityPresetChange(event) {
    const selectedDensity = event.target.value;
    const densityInput = document.getElementById("current_density");

    if (selectedDensity && densityInput) {
      densityInput.value = selectedDensity;
    }
  }

  // ページ移動
  goToPage(page) {
    if (page < 1 || (this.totalPages && page > this.totalPages)) {
      return;
    }
    this.currentPage = page;
    this.loadMaterials(this.currentFilters);
  }

  // ページネーション表示更新
  updatePagination() {
    // データがない場合はスキップ
    if (this.totalItems === undefined || this.totalItems === null) {
      console.log("総件数が未定義のためページネーション更新をスキップ");
      return;
    }

    // 新しいページネーション関数を使用
    if (this.totalItems > 0) {
      renderPagination('materials', this.currentPage, this.totalPages, (page) => {
        this.currentPage = page;
        this.fetchMaterials();
      });
    } else {
      // データがない場合はページネーションを非表示
      const topContainer = document.getElementById('materialsPaginationTop');
      const bottomContainer = document.getElementById('materialsPaginationBottom');
      if (topContainer) topContainer.innerHTML = '';
      if (bottomContainer) bottomContainer.innerHTML = '';
    }
  }

}

// グローバル変数として初期化
let materialManager;

// DOM読み込み完了後に初期化
document.addEventListener("DOMContentLoaded", () => {
  materialManager = new MaterialManager();
});
