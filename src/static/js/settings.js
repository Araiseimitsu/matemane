// 設定画面の JavaScript

class SettingsManager {
    constructor() {
        this.currentPresetId = null;
        this.init();
    }

    init() {
        this.loadDensityPresets();
        this.updateLastUpdated();
    }

    async loadDensityPresets() {
        try {
            const presets = await APIClient.get('/density-presets/');
            this.renderDensityPresets(presets);
        } catch (error) {
            console.error('比重プリセット取得エラー:', error);
            this.showAlert('比重プリセットの取得に失敗しました', 'danger');
        }
    }

    renderDensityPresets(presets) {
        const tbody = document.getElementById('density-presets-table');
        tbody.innerHTML = '';

        presets.forEach(preset => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${this.escapeHtml(preset.name)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${preset.density}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${this.escapeHtml(preset.description || '-')}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${new Date(preset.created_at).toLocaleDateString('ja-JP')}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button class="inline-flex items-center px-3 py-1 border border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-md text-sm font-medium transition-colors duration-200 mr-2" 
                            onclick="window.settingsManager.editDensityPreset(${preset.id})" 
                            title="編集">
                        <i class="fas fa-edit mr-1"></i>編集
                    </button>
                    <button class="inline-flex items-center px-3 py-1 border border-red-300 text-red-700 bg-red-50 hover:bg-red-100 rounded-md text-sm font-medium transition-colors duration-200" 
                            onclick="window.settingsManager.confirmDeletePreset(${preset.id}, '${this.escapeHtml(preset.name)}')" 
                            title="削除">
                        <i class="fas fa-trash mr-1"></i>削除
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    async editDensityPreset(presetId) {
        try {
            const preset = await APIClient.get(`/density-presets/${presetId}`);

            // フォームに値を設定
            document.getElementById('preset_id').value = preset.id;
            document.getElementById('preset_name').value = preset.name;
            document.getElementById('preset_density').value = preset.density;
            document.getElementById('preset_description').value = preset.description || '';

            // モーダルタイトルを変更
            document.getElementById('densityPresetModalTitle').textContent = '比重プリセット編集';

            // モーダルを表示
            const modal = document.getElementById('densityPresetModal');
            modal.classList.remove('hidden');

            this.currentPresetId = presetId;
        } catch (error) {
            console.error('比重プリセット取得エラー:', error);
            this.showAlert('比重プリセットの取得に失敗しました', 'danger');
        }
    }

    async saveDensityPreset() {
        const form = document.getElementById('densityPresetForm');
        const formData = new FormData(form);
        
        const data = {
            name: formData.get('name'),
            density: parseFloat(formData.get('density')),
            description: formData.get('description') || null
        };

        // バリデーション
        if (!data.name || !data.density || data.density <= 0) {
            this.showAlert('必須項目を正しく入力してください', 'warning');
            return;
        }

        try {
            let response;
            if (this.currentPresetId) {
                // 更新
                response = await APIClient.put(`/density-presets/${this.currentPresetId}`, data);
            } else {
                // 新規作成
                response = await APIClient.post('/density-presets/', data);
            }

            this.showAlert(
                this.currentPresetId ? '比重プリセットを更新しました' : '比重プリセットを作成しました',
                'success'
            );

            // モーダルを閉じて一覧を再読み込み
            const modal = document.getElementById('densityPresetModal');
            modal.classList.add('hidden');
            modal.classList.remove('flex');
            this.loadDensityPresets();

        } catch (error) {
            console.error('比重プリセット保存エラー:', error);
            const message = error.response?.data?.detail || '比重プリセットの保存に失敗しました';
            this.showAlert(message, 'danger');
        }
    }

    confirmDeletePreset(presetId, presetName) {
        this.currentPresetId = presetId;

        const modal = document.getElementById('deleteConfirmModal');
        modal.classList.remove('hidden');
    }

    async deleteDensityPreset() {
        if (!this.currentPresetId) return;

        try {
            await APIClient.delete(`/density-presets/${this.currentPresetId}`);
            this.showAlert('比重プリセットを削除しました', 'success');
            this.loadDensityPresets();
            
            // モーダルを閉じる
            const modal = document.getElementById('deleteConfirmModal');
            modal.classList.add('hidden');
        } catch (error) {
            console.error('比重プリセット削除エラー:', error);
            this.showAlert('比重プリセットの削除に失敗しました', 'danger');
        }
    }

    resetForm() {
        this.currentPresetId = null;
        document.getElementById('densityPresetForm').reset();
        document.getElementById('preset_id').value = '';
        document.getElementById('densityPresetModalTitle').textContent = '比重プリセット登録';
    }

    updateLastUpdated() {
        const now = new Date();
        document.getElementById('last-updated').textContent = now.toLocaleString('ja-JP');
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showAlert(message, type = 'info') {
        // Tailwind CSS用のアラート表示
        const alertContainer = document.createElement('div');
        alertContainer.className = 'fixed top-4 right-4 z-50';
        
        const alert = document.createElement('div');
        const bgColor = type === 'danger' ? 'bg-red-100 border-red-400 text-red-700' : 
                       type === 'success' ? 'bg-green-100 border-green-400 text-green-700' :
                       'bg-blue-100 border-blue-400 text-blue-700';
        
        alert.className = `${bgColor} px-4 py-3 rounded border shadow-lg max-w-sm`;
        alert.innerHTML = `
            <div class="flex items-center justify-between">
                <span>${message}</span>
                <button type="button" class="ml-4 text-gray-500 hover:text-gray-700" onclick="this.parentElement.parentElement.parentElement.remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        alertContainer.appendChild(alert);
        document.body.appendChild(alertContainer);

        // 5秒後に自動削除
        setTimeout(() => {
            if (alertContainer.parentNode) {
                alertContainer.remove();
            }
        }, 5000);
    }
}

// 初期化はsettings.htmlから行う