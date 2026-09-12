export type BusinessAccount = { businessId: string; email: string; businessName: string };
export type Channel = 'WHATSAPP'|'PHONE'|'SMS'|'EMAIL'|'INSTAGRAM'|'WEBSITE';
export type AppointmentStatus = 'PENDING'|'CONFIRMED'|'CANCELLED'|'COMPLETED'|'NO_SHOW';
export type ConversationStatus = 'ACTIVE'|'WAITING_CUSTOMER'|'WAITING_BUSINESS'|'CLOSED';

export type Identity = { id: string; channel: Channel; identifier: string; displayName: string|null; verified: boolean; isPrimary: boolean };
export type Customer = { id: string; name: string|null; identities: Identity[]; createdAt: string; updatedAt: string };
export type Appointment = { id:string; customerId:string; status:AppointmentStatus; scheduledStart:string; scheduledEnd:string; createdChannel:Channel; customerName:string|null; customerPhone:string|null; customerEmail:string|null };
export type Conversation = { id:string; customerId:string; customerName:string|null; channel:Channel; status:ConversationStatus; startedAt:string; lastMessageAt:string|null; lastMessage:string|null };
