import type { StateCreator } from "zustand";

export interface Notification {
  id: string;
  type: "info" | "success" | "warning" | "error";
  title: string;
  message: string;
  read: boolean;
  timestamp: number;
}

export interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
}

export interface NotificationActions {
  addNotification: (notification: Omit<Notification, "id" | "read" | "timestamp">) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  clearAll: () => void;
  removeNotification: (id: string) => void;
}

export type NotificationSlice = NotificationState & NotificationActions;

export const createNotificationSlice: StateCreator<
  NotificationSlice,
  [],
  [],
  NotificationSlice
> = (set) => ({
  notifications: [],
  unreadCount: 0,
  addNotification: (item) =>
    set((state) => {
      const newNotification: Notification = {
        ...item,
        id: `notif_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
        read: false,
        timestamp: Date.now(),
      };
      const notifications = [newNotification, ...state.notifications].slice(0, 50); // cap at 50
      return {
        notifications,
        unreadCount: notifications.filter((n) => !n.read).length,
      };
    }),
  markRead: (id) =>
    set((state) => {
      const notifications = state.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      );
      return {
        notifications,
        unreadCount: notifications.filter((n) => !n.read).length,
      };
    }),
  markAllRead: () =>
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    })),
  clearAll: () =>
    set({
      notifications: [],
      unreadCount: 0,
    }),
  removeNotification: (id) =>
    set((state) => {
      const notifications = state.notifications.filter((n) => n.id !== id);
      return {
        notifications,
        unreadCount: notifications.filter((n) => !n.read).length,
      };
    }),
});
