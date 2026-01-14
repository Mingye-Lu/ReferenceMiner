<script setup lang="ts">
defineProps<{
    title?: string
    message: string
    confirmText?: string
    cancelText?: string
}>()

const emit = defineEmits<{
    (event: 'confirm'): void
    (event: 'cancel'): void
}>()
</script>

<template>
    <div class="modal-backdrop" @click.self="emit('cancel')">
        <div class="modal-box">
            <div class="modal-header">
                <h3 class="modal-title">{{ title || 'Confirm' }}</h3>
                <button class="close-btn" @click="emit('cancel')">×</button>
            </div>
            <div class="modal-body">
                <p>{{ message }}</p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" @click="emit('cancel')">{{ cancelText || 'Cancel' }}</button>
                <button class="btn btn-danger" @click="emit('confirm')">{{ confirmText || 'Delete' }}</button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(2px);
    z-index: 200;
    display: flex;
    align-items: center;
    justify-content: center;
}

.modal-box {
    background: #fff;
    border-radius: 12px;
    width: 90%;
    max-width: 400px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
    display: flex;
    flex-direction: column;
}

.modal-header {
    padding: 16px 20px;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
}

.close-btn {
    background: none;
    border: none;
    font-size: 24px;
    color: #999;
    cursor: pointer;
    line-height: 1;
}

.modal-body {
    padding: 24px 20px;
    color: var(--text-primary);
    font-size: 14px;
    line-height: 1.5;
}

.modal-footer {
    padding: 16px 20px;
    background: #f9f9f9;
    border-radius: 0 0 12px 12px;
    display: flex;
    justify-content: flex-end;
    gap: 12px;
}

.btn {
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.2s;
}

.btn-secondary {
    background: #fff;
    border-color: #ddd;
    color: #333;
}

.btn-secondary:hover {
    background: #f5f5f5;
    border-color: #ccc;
}

.btn-danger {
    background: #fff0f0;
    color: #d32f2f;
    border-color: #ffcdd2;
}

.btn-danger:hover {
    background: #ffebee;
    border-color: #ef9a9a;
}
</style>
