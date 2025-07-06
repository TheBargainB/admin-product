"use client"

import * as React from "react"

export interface ToastOptions {
  title?: string
  description?: string
  variant?: "default" | "destructive"
  duration?: number
}

export interface Toast extends ToastOptions {
  id: string
}

let toastCounter = 0
const listeners = new Set<(toasts: Toast[]) => void>()
let toasts: Toast[] = []

function addToast(options: ToastOptions) {
  const id = `toast-${++toastCounter}`
  const toast: Toast = {
    ...options,
    id,
  }
  
  toasts = [...toasts, toast]
  listeners.forEach(listener => listener(toasts))
  
  // Auto-dismiss after duration
  const duration = options.duration || 5000
  setTimeout(() => {
    removeToast(id)
  }, duration)
  
  return id
}

function removeToast(id: string) {
  toasts = toasts.filter(toast => toast.id !== id)
  listeners.forEach(listener => listener(toasts))
}

export function useToast() {
  const [toastState, setToastState] = React.useState<Toast[]>([])
  
  React.useEffect(() => {
    listeners.add(setToastState)
    return () => {
      listeners.delete(setToastState)
    }
  }, [])
  
  return {
    toasts: toastState,
    addToast,
    removeToast,
    success: (options: Omit<ToastOptions, "variant">) => 
      addToast({ ...options, variant: "default" }),
    error: (options: Omit<ToastOptions, "variant">) => 
      addToast({ ...options, variant: "destructive" }),
    info: (options: Omit<ToastOptions, "variant">) => 
      addToast({ ...options, variant: "default" }),
  }
} 