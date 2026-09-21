import type { Lang } from '../api/types';

/**
 * Fixed language list for the switcher and Settings page — this is
 * independent of the currently-selected UI language, so it lives outside
 * `STRINGS`. Native names sourced from `services/orchestrator/i18n.py` /
 * `data/cities.json` conventions (the scripts each language is written in).
 */
export const LANGUAGES: { code: Lang; native: string; english: string }[] = [
  { code: 'en', native: 'English', english: 'English' },
  { code: 'ta', native: 'தமிழ்', english: 'Tamil' },
  { code: 'hi', native: 'हिन्दी', english: 'Hindi' },
  { code: 'te', native: 'తెలుగు', english: 'Telugu' },
  { code: 'mr', native: 'मराठी', english: 'Marathi' },
];

export interface UiStrings {
  // True only when a native speaker has confirmed this bundle's exact text.
  // The one native-speaker review so far (Sep 13, commit fce2ad9) covered the
  // hi/te/mr strings in services/orchestrator/i18n.py at that commit and
  // nothing in this file, which was authored on Sep 20 — so every Indic
  // bundle here is false, Tamil included. See web/README.md.
  nativeQa: boolean;

  // Nav / shell (authored, nativeQa: false — see web/README.md).
  navAsk: string;
  navDashboard: string;
  navWarnings: string;
  navSettings: string;

  // Ask page (authored).
  askTitle: string;
  askPlaceholder: string;
  askSubmit: string;
  cityFromQuestion: string;
  city: string;

  // Stat labels — sourced verbatim from services/orchestrator/i18n.py
  // `_CURRENT_PHRASES` (label portion, `{v}` and unit stripped). feelsLike and
  // humidity come from strings the Sep 13 review covered; uvIndex's source
  // string is itself `# TODO: native_qa` there.
  feelsLike: string;
  humidity: string;
  uvIndex: string;
  wind: string; // authored — not in _CURRENT_PHRASES.

  // Warnings page (authored). Colour words, colour meanings and category
  // labels are NOT here: the API serves them from data/i18n/glossary.json
  // (`legend`, `warning.colour_label`, `warning.category_label` on
  // /warnings) so there is one copy of that text, not three.
  alert: string;
  warningsUnavailable: string;
  noWarningBody: string;
  valid: string;
  unknownCity: string;

  // Generic states (authored).
  loading: string;
  retry: string;
  errNetwork: string;
  errTimeout: string;
  errRate: string;
  errHttp: string;
  templateAnswer: string;
  fixtureData: string;
  liveData: string;
  notReported: string;

  // Settings (authored).
  language: string;
  defaultCity: string;
  saved: string;
  aboutData: string;
  cityImage: string;
  notFound: string;

  // Ask page example chips — sourced verbatim from ml/nlu/eval_set.jsonl
  // rows 001-003 for this language. Those rows are flagged native_qa: false
  // for every language but English, so copying them confers no review.
  exampleQueries: [string, string, string];
}

export const STRINGS: Record<Lang, UiStrings> = {
  en: {
    nativeQa: true,
    navAsk: 'Ask',
    navDashboard: 'Dashboard',
    navWarnings: 'Warnings',
    navSettings: 'Settings',
    askTitle: 'Ask about the weather',
    askPlaceholder: "What's the weather in Chennai?",
    askSubmit: 'Ask',
    cityFromQuestion: 'City from question',
    city: 'City',
    feelsLike: 'Feels like',
    humidity: 'Humidity',
    uvIndex: 'UV index',
    wind: 'Wind',
    alert: 'Alert',
    warningsUnavailable:
      "Warnings aren't available right now — the IMD warning feed isn't connected. This is not an all-clear.",
    noWarningBody: 'No IMD warning is currently active for',
    valid: 'Valid',
    unknownCity: "That city isn't tracked yet.",
    loading: 'Loading…',
    retry: 'Retry',
    errNetwork: "Couldn't reach the server.",
    errTimeout: 'The request took too long.',
    errRate: 'Too many requests — try again shortly.',
    errHttp: 'The server returned an error',
    templateAnswer: 'This is a template answer, not model-generated.',
    fixtureData: 'fixture',
    liveData: 'live',
    notReported: 'not reported',
    language: 'Language',
    defaultCity: 'Default city',
    saved: 'Saved',
    aboutData: 'About this data',
    cityImage: 'City skyline',
    notFound: "This page doesn't exist.",
    exampleQueries: [
      "what's the weather in Chennai",
      'current weather in Madurai',
      'weather in Coimbatore right now',
    ],
  },
  ta: {
    // Authored Sep 20 (commit 94b87f7): not reverse-engineered from Bhashini
    // output like the i18n.py Tamil strings, and never native-reviewed
    // (audit item 4.2).
    nativeQa: false,
    navAsk: 'கேள்வி',
    navDashboard: 'டாஷ்போர்டு',
    navWarnings: 'எச்சரிக்கைகள்',
    navSettings: 'அமைப்புகள்',
    askTitle: 'வானிலை பற்றி கேளுங்கள்',
    askPlaceholder: 'சென்னையில் வானிலை எப்படி இருக்கிறது?',
    askSubmit: 'கேள்',
    cityFromQuestion: 'கேள்வியிலிருந்து நகரம்',
    city: 'நகரம்',
    feelsLike: 'உணரப்படுவது',
    humidity: 'ஈரப்பதம்',
    uvIndex: 'UV குறியீடு',
    wind: 'காற்று',
    alert: 'எச்சரிக்கை',
    warningsUnavailable:
      'எச்சரிக்கைகள் இப்போது கிடைக்கவில்லை — IMD எச்சரிக்கை சேவை இணைக்கப்படவில்லை. இது ஆபத்து இல்லை என்பதற்கான உறுதி அல்ல.',
    noWarningBody: 'தற்போது எந்த IMD எச்சரிக்கையும் இயங்கவில்லை',
    valid: 'செல்லுபடி',
    unknownCity: 'இந்த நகரம் இன்னும் கண்காணிக்கப்படவில்லை.',
    loading: 'ஏற்றுகிறது…',
    retry: 'மீண்டும் முயற்சி செய்',
    errNetwork: 'சேவையகத்தை அடைய முடியவில்லை.',
    errTimeout: 'கோரிக்கை அதிக நேரம் எடுத்தது.',
    errRate: 'அதிக கோரிக்கைகள் — சிறிது நேரம் கழித்து முயற்சிக்கவும்.',
    errHttp: 'சேவையகம் பிழையை அளித்தது',
    templateAnswer: 'இது ஒரு மாதிரி பதில், மாடல் உருவாக்கியது அல்ல.',
    fixtureData: 'மாதிரி தரவு',
    liveData: 'நேரடி',
    notReported: 'தெரிவிக்கப்படவில்லை',
    language: 'மொழி',
    defaultCity: 'இயல்புநிலை நகரம்',
    saved: 'சேமிக்கப்பட்டது',
    aboutData: 'இந்த தரவு பற்றி',
    cityImage: 'நகர அடிவானம்',
    notFound: 'இந்தப் பக்கம் இல்லை.',
    exampleQueries: [
      'நாளை சென்னையில் மழை பெய்யுமா?',
      'இன்று மதுரையில் மழை வருமா?',
      'இன்றிரவு கோயம்புத்தூரில் மழை பெய்யுமா?',
    ],
  },
  hi: {
    nativeQa: false,
    navAsk: 'पूछें',
    navDashboard: 'डैशबोर्ड',
    navWarnings: 'चेतावनियां',
    navSettings: 'सेटिंग्स',
    askTitle: 'मौसम के बारे में पूछें',
    askPlaceholder: 'चेन्नई में मौसम कैसा है?',
    askSubmit: 'पूछें',
    cityFromQuestion: 'प्रश्न से शहर',
    city: 'शहर',
    feelsLike: 'महसूस होता है',
    humidity: 'आर्द्रता',
    uvIndex: 'यूवी इंडेक्स',
    wind: 'हवा',
    alert: 'चेतावनी',
    warningsUnavailable:
      'चेतावनियां अभी उपलब्ध नहीं हैं — IMD चेतावनी सेवा जुड़ी नहीं है। इसका मतलब यह नहीं है कि कोई खतरा नहीं है।',
    noWarningBody: 'फिलहाल कोई IMD चेतावनी सक्रिय नहीं है',
    valid: 'मान्य',
    unknownCity: 'यह शहर अभी ट्रैक नहीं किया जाता।',
    loading: 'लोड हो रहा है…',
    retry: 'फिर से कोशिश करें',
    errNetwork: 'सर्वर तक नहीं पहुंच सका।',
    errTimeout: 'अनुरोध में बहुत समय लगा।',
    errRate: 'बहुत अधिक अनुरोध — कुछ देर बाद पुनः प्रयास करें।',
    errHttp: 'सर्वर ने त्रुटि लौटाई',
    templateAnswer: 'यह एक टेम्पलेट उत्तर है, मॉडल-जनित नहीं।',
    fixtureData: 'नमूना डेटा',
    liveData: 'लाइव',
    notReported: 'रिपोर्ट नहीं किया गया',
    language: 'भाषा',
    defaultCity: 'डिफ़ॉल्ट शहर',
    saved: 'सहेजा गया',
    aboutData: 'इस डेटा के बारे में',
    cityImage: 'शहर की क्षितिज रेखा',
    notFound: 'यह पृष्ठ मौजूद नहीं है।',
    exampleQueries: [
      'कल चेन्नई में बारिश होगी क्या?',
      'मदुरै में आज मौसम कैसा है?',
      'कोयंबटूर में आज कितनी बारिश हुई है?',
    ],
  },
  te: {
    nativeQa: false,
    navAsk: 'అడగండి',
    navDashboard: 'డాష్‌బోర్డ్',
    navWarnings: 'హెచ్చరికలు',
    navSettings: 'సెట్టింగ్‌లు',
    askTitle: 'వాతావరణం గురించి అడగండి',
    askPlaceholder: 'చెన్నైలో వాతావరణం ఎలా ఉంది?',
    askSubmit: 'అడుగు',
    cityFromQuestion: 'ప్రశ్న నుండి నగరం',
    city: 'నగరం',
    feelsLike: 'అనుభూతి',
    humidity: 'తేమ',
    uvIndex: 'యూవీ సూచిక',
    wind: 'గాలి',
    alert: 'హెచ్చరిక',
    warningsUnavailable:
      'హెచ్చరికలు ప్రస్తుతం అందుబాటులో లేవు — IMD హెచ్చరిక సేవ అనుసంధానించబడలేదు. దీని అర్థం ప్రమాదం లేదని కాదు.',
    noWarningBody: 'ప్రస్తుతం ఏ IMD హెచ్చరిక అమలులో లేదు',
    valid: 'చెల్లుబాటు',
    unknownCity: 'ఈ నగరం ఇంకా ట్రాక్ చేయబడలేదు.',
    loading: 'లోడ్ అవుతోంది…',
    retry: 'మళ్ళీ ప్రయత్నించండి',
    errNetwork: 'సర్వర్‌ను చేరుకోలేకపోయాము.',
    errTimeout: 'అభ్యర్థన చాలా సమయం తీసుకుంది.',
    errRate: 'చాలా అభ్యర్థనలు — కొద్దిసేపటి తర్వాత మళ్ళీ ప్రయత్నించండి.',
    errHttp: 'సర్వర్ లోపాన్ని తిరిగి ఇచ్చింది',
    templateAnswer: 'ఇది టెంప్లేట్ సమాధానం, మోడల్-జనరేటెడ్ కాదు.',
    fixtureData: 'నమూనా డేటా',
    liveData: 'ప్రత్యక్ష',
    notReported: 'నివేదించబడలేదు',
    language: 'భాష',
    defaultCity: 'డిఫాల్ట్ నగరం',
    saved: 'సేవ్ చేయబడింది',
    aboutData: 'ఈ డేటా గురించి',
    cityImage: 'నగర స్కైలైన్',
    notFound: 'ఈ పేజీ లేదు.',
    exampleQueries: [
      'రేపు చెన్నైలో వర్షం పడుతుందా?',
      'మదురైలో ఇప్పుడు వాతావరణం ఎలా ఉంది?',
      'కోయంబత్తూరులో ఈరోజు ఇప్పటివరకు ఎంత వర్షం పడింది?',
    ],
  },
  mr: {
    nativeQa: false,
    navAsk: 'विचारा',
    navDashboard: 'डॅशबोर्ड',
    navWarnings: 'इशारे',
    navSettings: 'सेटिंग्ज',
    askTitle: 'हवामानाबद्दल विचारा',
    askPlaceholder: 'चेन्नईमध्ये हवामान कसे आहे?',
    askSubmit: 'विचारा',
    cityFromQuestion: 'प्रश्नातील शहर',
    city: 'शहर',
    feelsLike: 'जाणवते',
    humidity: 'आर्द्रता',
    uvIndex: 'यूव्ही निर्देशांक',
    wind: 'वारा',
    alert: 'इशारा',
    warningsUnavailable:
      'इशारे सध्या उपलब्ध नाहीत — IMD इशारा सेवा जोडलेली नाही. याचा अर्थ धोका नाही असा नाही.',
    noWarningBody: 'सध्या कोणताही IMD इशारा सक्रिय नाही',
    valid: 'वैध',
    unknownCity: 'हे शहर अद्याप ट्रॅक केलेले नाही.',
    loading: 'लोड होत आहे…',
    retry: 'पुन्हा प्रयत्न करा',
    errNetwork: 'सर्व्हरपर्यंत पोहोचता आले नाही.',
    errTimeout: 'विनंतीला जास्त वेळ लागला.',
    errRate: 'खूप विनंत्या — थोड्या वेळाने पुन्हा प्रयत्न करा.',
    errHttp: 'सर्व्हरने त्रुटी परत केली',
    templateAnswer: 'हे एक टेम्पलेट उत्तर आहे, मॉडेल-निर्मित नाही.',
    fixtureData: 'नमुना डेटा',
    liveData: 'थेट',
    notReported: 'नोंदवलेले नाही',
    language: 'भाषा',
    defaultCity: 'डीफॉल्ट शहर',
    saved: 'जतन केले',
    aboutData: 'या डेटाबद्दल',
    cityImage: 'शहर स्कायलाइन',
    notFound: 'हे पान अस्तित्वात नाही.',
    exampleQueries: [
      'उद्या चेन्नईत पाऊस पडेल का?',
      'मदुराईत आज हवामान कसे आहे?',
      'कोईम्बतूरमध्ये आजपर्यंत किती पाऊस पडला?',
    ],
  },
};

export function useT(lang: Lang): UiStrings {
  const strings = STRINGS[lang];
  const fallback = STRINGS.en;
  return new Proxy(strings, {
    get(target, prop, receiver) {
      const value = Reflect.get(target, prop, receiver);
      if (value === undefined) return Reflect.get(fallback, prop);
      return value;
    },
  });
}
