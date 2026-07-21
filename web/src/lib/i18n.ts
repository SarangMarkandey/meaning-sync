import type { LanguageCode } from "@/lib/api";

const en = {
  preferences: "Preferences",
  participation: "Participation",
  conversation: "Conversation",
  checkUnderstanding: "Check understanding",
  confirm: "Confirm",
  receipt: "Receipt",
  currentStep: "Current step",
  talkTitle: "Talk about the agreement",
  talkHelp: "Have a normal service conversation, then review it together.",
  type: "Type",
  speak: "Speak",
  sendMessage: "Send message",
  ready: "I’m ready to review",
  keepTalking: "Keep talking",
  compare: "Compare our understanding",
  waiting: "Waiting for the other person…",
  translationPending: "Translation is being prepared…",
  translationFailed: "Translation is unavailable. The original remains visible.",
  retryTranslation: "Retry translation",
  original: "Original",
  translated: "Translated view",
  leaveUnresolved: "Leave unresolved",
  confirmationStatement: "I confirm that this reflects my understanding.",
  confirmMine: "Confirm my understanding",
  clarityReceipt: "Clarity receipt",
  microphoneUnavailable: "The microphone could not be started. Continue with text.",
} as const;

type TranslationKey = keyof typeof en;

const hi: Record<TranslationKey, string> = {
  preferences: "प्राथमिकताएँ",
  participation: "भागीदारी",
  conversation: "बातचीत",
  checkUnderstanding: "समझ जाँचें",
  confirm: "पुष्टि करें",
  receipt: "रसीद",
  currentStep: "वर्तमान चरण",
  talkTitle: "सहमति के बारे में बात करें",
  talkHelp: "सामान्य बातचीत करें, फिर उसे साथ में जाँचें।",
  type: "लिखें",
  speak: "बोलें",
  sendMessage: "संदेश भेजें",
  ready: "मैं समीक्षा के लिए तैयार हूँ",
  keepTalking: "बातचीत जारी रखें",
  compare: "हमारी समझ की तुलना करें",
  waiting: "दूसरे प्रतिभागी की प्रतीक्षा हो रही है…",
  translationPending: "अनुवाद तैयार हो रहा है…",
  translationFailed: "अनुवाद उपलब्ध नहीं है। मूल कथन दिखाई देता रहेगा।",
  retryTranslation: "अनुवाद फिर से करें",
  original: "मूल कथन",
  translated: "अनुवादित रूप",
  leaveUnresolved: "अनसुलझा छोड़ें",
  confirmationStatement: "मैं पुष्टि करता/करती हूँ कि यह मेरी समझ को सही रूप से दर्शाता है।",
  confirmMine: "अपनी समझ की पुष्टि करें",
  clarityReceipt: "स्पष्टता रसीद",
  microphoneUnavailable: "माइक्रोफ़ोन शुरू नहीं हो सका। लिखकर जारी रखें।",
};

const dictionaries = { en, hi } satisfies Record<LanguageCode, Record<TranslationKey, string>>;

export function t(language: LanguageCode, key: TranslationKey): string {
  const value = dictionaries[language]?.[key];
  if (!value) {
    if (process.env.NODE_ENV === "development") {
      console.warn(`Missing MeaningSync translation: ${language}.${key}`);
    }
    return en[key];
  }
  return value;
}

export function languageName(language: LanguageCode): string {
  return language === "hi" ? "हिंदी" : "English";
}
