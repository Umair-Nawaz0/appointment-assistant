export type BusinessAccount = { businessId: string; email: string; businessName: string };
export type AppointmentStatus = 'PENDING' | 'CONFIRMED' | 'CANCELLED' | 'COMPLETED' | 'NO_SHOW';
export type ConversationStatus = 'ACTIVE' | 'WAITING_CUSTOMER' | 'WAITING_BUSINESS' | 'CLOSED';

export type Customer = {
  id: string;
  name: string | null;
  phone: string | null;
  email: string | null;
  createdAt: string;
  updatedAt: string;
};

export type Appointment = {
  id: string;
  customerId: string;
  conversationId?: string | null;
  status: AppointmentStatus;
  scheduledStart: string;
  scheduledEnd: string;
  customerName: string | null;
  customerPhone: string | null;
  customerEmail: string | null;
};

export type Conversation = {
  id: string;
  customerId: string | null;
  customerName: string | null;
  status: ConversationStatus;
  startedAt: string;
  lastMessageAt: string | null;
  lastMessage: string | null;
};
