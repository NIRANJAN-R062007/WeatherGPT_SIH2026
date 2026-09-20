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
  // `_CURRENT_PHRASES` (label portion, `{v}` and unit stripped).
  feelsLike: string;
  humidity: string;
  uvIndex: string;
  wind: string; // authored — not in _CURRENT_PHRASES.

  // Warnings page (authored, except colour_* and noWarning below).
  alert: string;
  noWarningBody: string;
  valid: string;
  unknownCity: string;

  // Sourced verbatim from data/i18n/glossary.json.
  noWarning: string; // category_no_warning
  colourMeaningGreen: string; // colour_green
  colourMeaningYellow: string; // colour_yellow
  colourMeaningOrange: string; // colour_orange
  colourMeaningRed: string; // colour_red
  colourGreen: string; // colour word extracted from colour_green
  colourYellow: string;
  colourOrange: string;
  colourRed: string;

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
  // rows 001-003 for this language.
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
    noWarningBody: 'No IMD warning is currently active for',
    valid: 'Valid',
    unknownCity: "That city isn't tracked yet.",
    noWarning: 'No warning in force',
    colourMeaningGreen:
      'Green means no warning: no significant severe weather is expected, so no specific action is needed beyond normal precautions.',
    colourMeaningYellow:
      'Yellow means watch and stay updated: be aware of developing weather conditions and keep checking for the latest forecasts, as the situation could worsen.',
    colourMeaningOrange:
      'Orange means be prepared: severe weather is likely, so people should stay alert, prepare for disruption, and follow guidance from local authorities.',
    colourMeaningRed:
      'Red means take action: very severe weather is expected, so people should follow official advisories, avoid unnecessary travel, and take protective action immediately.',
    colourGreen: 'Green',
    colourYellow: 'Yellow',
    colourOrange: 'Orange',
    colourRed: 'Red',
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
    nativeQa: true,
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
    noWarningBody: 'தற்போது எந்த IMD எச்சரிக்கையும் இயங்கவில்லை',
    valid: 'செல்லுபடி',
    unknownCity: 'இந்த நகரம் இன்னும் கண்காணிக்கப்படவில்லை.',
    noWarning: 'எச்சரிக்கை இல்லை',
    colourMeaningGreen:
      'பச்சை என்பது எச்சரிக்கை இல்லை என்பதைக் குறிக்கிறது: குறிப்பிடத்தக்க கடுமையான வானிலை எதிர்பார்க்கப்படவில்லை, எனவே வழக்கமான முன்னெச்சரிக்கைகளைத் தவிர வேறு நடவடிக்கை தேவையில்லை.',
    colourMeaningYellow:
      'மஞ்சள் என்பது கவனமாக இருங்கள், புதுப்பிப்புகளைப் பின்பற்றுங்கள் என்பதைக் குறிக்கிறது: வளர்ந்து வரும் வானிலை நிலைமைகளை அறிந்திருங்கள், நிலைமை மோசமடையக்கூடும் என்பதால் சமீபத்திய முன்னறிவிப்புகளைத் தொடர்ந்து சரிபார்க்கவும்.',
    colourMeaningOrange:
      'ஆரஞ்சு என்பது தயாராக இருங்கள் என்பதைக் குறிக்கிறது: கடுமையான வானிலை ஏற்படும் வாய்ப்புள்ளது, எனவே மக்கள் விழிப்புடன் இருந்து, இடையூறுகளுக்குத் தயாராகி, உள்ளூர் அதிகாரிகளின் வழிகாட்டுதலைப் பின்பற்ற வேண்டும்.',
    colourMeaningRed:
      'சிவப்பு என்பது நடவடிக்கை எடுங்கள் என்பதைக் குறிக்கிறது: மிகக் கடுமையான வானிலை எதிர்பார்க்கப்படுகிறது, எனவே மக்கள் அதிகாரப்பூர்வ ஆலோசனைகளைப் பின்பற்றி, தேவையற்ற பயணத்தைத் தவிர்த்து, உடனடியாக பாதுகாப்பு நடவடிக்கை எடுக்க வேண்டும்.',
    colourGreen: 'பச்சை',
    colourYellow: 'மஞ்சள்',
    colourOrange: 'ஆரஞ்சு',
    colourRed: 'சிவப்பு',
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
    noWarningBody: 'फिलहाल कोई IMD चेतावनी सक्रिय नहीं है',
    valid: 'मान्य',
    unknownCity: 'यह शहर अभी ट्रैक नहीं किया जाता।',
    noWarning: 'कोई चेतावनी नहीं',
    colourMeaningGreen:
      'हरा रंग दर्शाता है कि कोई चेतावनी नहीं है: किसी गंभीर खराब मौसम की आशंका नहीं है, इसलिए सामान्य सावधानियों के अलावा किसी विशेष कार्रवाई की आवश्यकता नहीं है।',
    colourMeaningYellow:
      'पीला रंग दर्शाता है कि सतर्क रहें और अपडेट रहें: बदलते मौसम की स्थिति पर ध्यान दें और नवीनतम पूर्वानुमान लगातार देखते रहें, क्योंकि स्थिति और बिगड़ सकती है।',
    colourMeaningOrange:
      'नारंगी रंग दर्शाता है कि तैयार रहें: गंभीर मौसम की संभावना है, इसलिए लोगों को सतर्क रहना चाहिए, व्यवधान के लिए तैयार रहना चाहिए और स्थानीय अधिकारियों के मार्गदर्शन का पालन करना चाहिए।',
    colourMeaningRed:
      'लाल रंग दर्शाता है कि कार्रवाई करें: बहुत गंभीर मौसम की आशंका है, इसलिए लोगों को आधिकारिक सलाह का पालन करना चाहिए, अनावश्यक यात्रा से बचना चाहिए और तुरंत सुरक्षात्मक कदम उठाने चाहिए।',
    colourGreen: 'हरा',
    colourYellow: 'पीला',
    colourOrange: 'नारंगी',
    colourRed: 'लाल',
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
    noWarningBody: 'ప్రస్తుతం ఏ IMD హెచ్చరిక అమలులో లేదు',
    valid: 'చెల్లుబాటు',
    unknownCity: 'ఈ నగరం ఇంకా ట్రాక్ చేయబడలేదు.',
    noWarning: 'హెచ్చరిక లేదు',
    colourMeaningGreen:
      'ఆకుపచ్చ రంగు హెచ్చరిక లేదని సూచిస్తుంది: ముఖ్యమైన తీవ్ర వాతావరణం ఆశించబడదు, కాబట్టి సాధారణ జాగ్రత్తలు తప్ప ప్రత్యేక చర్య అవసరం లేదు.',
    colourMeaningYellow:
      'పసుపు రంగు అప్రమత్తంగా ఉండి తాజా సమాచారం తెలుసుకోమని సూచిస్తుంది: అభివృద్ధి చెందుతున్న వాతావరణ పరిస్థితులపై అవగాహన కలిగి ఉండండి మరియు పరిస్థితి మరింత దిగజారవచ్చు కాబట్టి తాజా సూచనలను ఎప్పటికప్పుడు తనిఖీ చేయండి.',
    colourMeaningOrange:
      'నారింజ రంగు సిద్ధంగా ఉండమని సూచిస్తుంది: తీవ్రమైన వాతావరణం అవకాశం ఉంది, కాబట్టి ప్రజలు అప్రమత్తంగా ఉండి, అంతరాయాలకు సిద్ధంగా ఉండి, స్థానిక అధికారుల మార్గదర్శకాలను పాటించాలి.',
    colourMeaningRed:
      'ఎరుపు రంగు చర్య తీసుకోమని సూచిస్తుంది: అత్యంత తీవ్రమైన వాతావరణం ఆశించబడుతోంది, కాబట్టి ప్రజలు అధికారిక సూచనలను పాటించి, అనవసర ప్రయాణాన్ని నివారించి, వెంటనే రక్షణ చర్యలు తీసుకోవాలి.',
    colourGreen: 'ఆకుపచ్చ',
    colourYellow: 'పసుపు',
    colourOrange: 'నారింజ',
    colourRed: 'ఎరుపు',
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
    noWarningBody: 'सध्या कोणताही IMD इशारा सक्रिय नाही',
    valid: 'वैध',
    unknownCity: 'हे शहर अद्याप ट्रॅक केलेले नाही.',
    noWarning: 'कोणताही इशारा नाही',
    colourMeaningGreen:
      'हिरवा रंग म्हणजे कोणताही इशारा नाही: कोणत्याही गंभीर हवामानाची शक्यता नाही, त्यामुळे नेहमीच्या खबरदारीशिवाय विशेष कृतीची गरज नाही.',
    colourMeaningYellow:
      'पिवळा रंग म्हणजे सतर्क राहा आणि माहिती अद्ययावत ठेवा: विकसित होत असलेल्या हवामान परिस्थितीची जाणीव ठेवा आणि परिस्थिती अधिक बिघडू शकते म्हणून नवीनतम अंदाज सतत तपासत रहा.',
    colourMeaningOrange:
      'नारिंगी रंग म्हणजे तयार राहा: गंभीर हवामानाची शक्यता आहे, त्यामुळे लोकांनी सतर्क राहावे, अडथळ्यांसाठी तयार राहावे आणि स्थानिक प्रशासनाच्या सूचनांचे पालन करावे.',
    colourMeaningRed:
      'लाल रंग म्हणजे कृती करा: अत्यंत तीव्र हवामानाची शक्यता आहे, त्यामुळे लोकांनी अधिकृत सूचनांचे पालन करावे, अनावश्यक प्रवास टाळावा आणि त्वरित संरक्षणात्मक उपाययोजना कराव्यात.',
    colourGreen: 'हिरवा',
    colourYellow: 'पिवळा',
    colourOrange: 'नारिंगी',
    colourRed: 'लाल',
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
