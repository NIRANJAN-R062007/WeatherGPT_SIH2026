// The onboarding screens' text (Languages → Welcome + Log In) in the five
// app languages. The Languages page shows it in the language being picked,
// and the Welcome page in the one picked. web/src/lib/onboardingStrings.ts
// carries the same table — keep the two in step.
//
// TODO: native_qa — the hi/ta/te/mr strings below are author-written and
// have not been reviewed by a native speaker yet.

class OnboardingStrings {
  final String languagesTitle;
  final String languagesLead;
  final String continueLabel;

  /// "Welcome to WeatherGPT!" in three parts: a small line above the brand,
  /// what follows "WeatherGPT" on the large line (the "!" in English, a case
  /// ending elsewhere), and a small line below it.
  final String welcomeBefore;
  final String welcomeBrandSuffix;
  final String welcomeAfter;

  final String emailOrPhone;
  final String password;
  final String forgotPassword;
  final String logIn;
  final String or;
  final String continueWithGoogle;
  final String waitingForGoogle;
  final String noAccount;
  final String signUp;
  final String guest;

  final String enterEmailOrPhone;
  final String badEmail;
  final String phoneUnavailable;
  final String enterPassword;
  final String showPassword;
  final String hidePassword;
  final String resendConfirmation;
  final String confirmationResent;
  final String back;
  final String lightMode;
  final String darkMode;

  const OnboardingStrings({
    required this.languagesTitle,
    required this.languagesLead,
    required this.continueLabel,
    required this.welcomeBefore,
    required this.welcomeBrandSuffix,
    required this.welcomeAfter,
    required this.emailOrPhone,
    required this.password,
    required this.forgotPassword,
    required this.logIn,
    required this.or,
    required this.continueWithGoogle,
    required this.waitingForGoogle,
    required this.noAccount,
    required this.signUp,
    required this.guest,
    required this.enterEmailOrPhone,
    required this.badEmail,
    required this.phoneUnavailable,
    required this.enterPassword,
    required this.showPassword,
    required this.hidePassword,
    required this.resendConfirmation,
    required this.confirmationResent,
    required this.back,
    required this.lightMode,
    required this.darkMode,
  });

  /// The whole welcome line, for screen readers.
  String get welcome =>
      [welcomeBefore, 'WeatherGPT$welcomeBrandSuffix', welcomeAfter].where((s) => s.isNotEmpty).join(' ');

  static OnboardingStrings of(String lang) => kOnboardingStrings[lang] ?? kOnboardingStrings['en']!;
}

const Map<String, OnboardingStrings> kOnboardingStrings = {
  'en': OnboardingStrings(
    languagesTitle: 'Languages',
    languagesLead: 'Choose your preferred language to get started.',
    continueLabel: 'Continue',
    welcomeBefore: 'Welcome to',
    welcomeBrandSuffix: '!',
    welcomeAfter: '',
    emailOrPhone: 'Email or phone number',
    password: 'Password',
    forgotPassword: 'Forgot password?',
    logIn: 'Log In',
    or: 'or',
    continueWithGoogle: 'Continue with Google',
    waitingForGoogle: 'Waiting for Google…',
    noAccount: "Don't have an account?",
    signUp: 'Sign Up',
    guest: 'Sign in as Guest',
    enterEmailOrPhone: 'Enter your email or phone number.',
    badEmail: "That doesn't look like an email address.",
    phoneUnavailable: "Phone sign-in isn't available yet — please use your email.",
    enterPassword: 'Enter your password.',
    showPassword: 'Show password',
    hidePassword: 'Hide password',
    resendConfirmation: 'Resend confirmation email',
    confirmationResent: 'Confirmation email sent again.',
    back: 'Back',
    lightMode: 'Light mode',
    darkMode: 'Dark mode',
  ),
  'hi': OnboardingStrings(
    languagesTitle: 'भाषाएँ',
    languagesLead: 'शुरू करने के लिए अपनी पसंदीदा भाषा चुनें।',
    continueLabel: 'आगे बढ़ें',
    welcomeBefore: '',
    welcomeBrandSuffix: ' में',
    welcomeAfter: 'आपका स्वागत है!',
    emailOrPhone: 'ईमेल या फ़ोन नंबर',
    password: 'पासवर्ड',
    forgotPassword: 'पासवर्ड भूल गए?',
    logIn: 'लॉग इन करें',
    or: 'या',
    continueWithGoogle: 'Google के साथ जारी रखें',
    waitingForGoogle: 'Google की प्रतीक्षा…',
    noAccount: 'खाता नहीं है?',
    signUp: 'साइन अप करें',
    guest: 'अतिथि के रूप में साइन इन करें',
    enterEmailOrPhone: 'अपना ईमेल या फ़ोन नंबर दर्ज करें।',
    badEmail: 'यह ईमेल पता सही नहीं लगता।',
    phoneUnavailable: 'फ़ोन से साइन इन अभी उपलब्ध नहीं है — कृपया अपना ईमेल इस्तेमाल करें।',
    enterPassword: 'अपना पासवर्ड दर्ज करें।',
    showPassword: 'पासवर्ड दिखाएँ',
    hidePassword: 'पासवर्ड छिपाएँ',
    resendConfirmation: 'पुष्टि ईमेल फिर से भेजें',
    confirmationResent: 'पुष्टि ईमेल फिर से भेज दिया गया।',
    back: 'वापस',
    lightMode: 'लाइट मोड',
    darkMode: 'डार्क मोड',
  ),
  'ta': OnboardingStrings(
    languagesTitle: 'மொழிகள்',
    languagesLead: 'தொடங்க உங்களுக்கு விருப்பமான மொழியைத் தேர்ந்தெடுக்கவும்.',
    continueLabel: 'தொடரவும்',
    welcomeBefore: '',
    welcomeBrandSuffix: '-க்கு',
    welcomeAfter: 'வரவேற்கிறோம்!',
    emailOrPhone: 'மின்னஞ்சல் அல்லது தொலைபேசி எண்',
    password: 'கடவுச்சொல்',
    forgotPassword: 'கடவுச்சொல் மறந்துவிட்டதா?',
    logIn: 'உள்நுழைக',
    or: 'அல்லது',
    continueWithGoogle: 'Google மூலம் தொடரவும்',
    waitingForGoogle: 'Google-க்காகக் காத்திருக்கிறது…',
    noAccount: 'கணக்கு இல்லையா?',
    signUp: 'பதிவு செய்க',
    guest: 'விருந்தினராக உள்நுழைக',
    enterEmailOrPhone: 'உங்கள் மின்னஞ்சல் அல்லது தொலைபேசி எண்ணை உள்ளிடவும்.',
    badEmail: 'இது சரியான மின்னஞ்சல் முகவரியாகத் தெரியவில்லை.',
    phoneUnavailable: 'தொலைபேசி மூலம் உள்நுழைவு இன்னும் கிடைக்கவில்லை — உங்கள் மின்னஞ்சலைப் பயன்படுத்தவும்.',
    enterPassword: 'உங்கள் கடவுச்சொல்லை உள்ளிடவும்.',
    showPassword: 'கடவுச்சொல்லைக் காட்டு',
    hidePassword: 'கடவுச்சொல்லை மறை',
    resendConfirmation: 'உறுதிப்படுத்தல் மின்னஞ்சலை மீண்டும் அனுப்பு',
    confirmationResent: 'உறுதிப்படுத்தல் மின்னஞ்சல் மீண்டும் அனுப்பப்பட்டது.',
    back: 'பின் செல்',
    lightMode: 'லைட் பயன்முறை',
    darkMode: 'டார்க் பயன்முறை',
  ),
  'te': OnboardingStrings(
    languagesTitle: 'భాషలు',
    languagesLead: 'ప్రారంభించడానికి మీకు నచ్చిన భాషను ఎంచుకోండి.',
    continueLabel: 'కొనసాగించండి',
    welcomeBefore: '',
    welcomeBrandSuffix: 'కి',
    welcomeAfter: 'స్వాగతం!',
    emailOrPhone: 'ఇమెయిల్ లేదా ఫోన్ నంబర్',
    password: 'పాస్‌వర్డ్',
    forgotPassword: 'పాస్‌వర్డ్ మర్చిపోయారా?',
    logIn: 'లాగిన్ చేయండి',
    or: 'లేదా',
    continueWithGoogle: 'Googleతో కొనసాగించండి',
    waitingForGoogle: 'Google కోసం వేచి ఉంది…',
    noAccount: 'ఖాతా లేదా?',
    signUp: 'సైన్ అప్ చేయండి',
    guest: 'అతిథిగా సైన్ ఇన్ చేయండి',
    enterEmailOrPhone: 'మీ ఇమెయిల్ లేదా ఫోన్ నంబర్ నమోదు చేయండి.',
    badEmail: 'ఇది సరైన ఇమెయిల్ చిరునామాలా లేదు.',
    phoneUnavailable: 'ఫోన్‌తో సైన్ ఇన్ ఇంకా అందుబాటులో లేదు — దయచేసి మీ ఇమెయిల్ ఉపయోగించండి.',
    enterPassword: 'మీ పాస్‌వర్డ్ నమోదు చేయండి.',
    showPassword: 'పాస్‌వర్డ్ చూపించు',
    hidePassword: 'పాస్‌వర్డ్ దాచు',
    resendConfirmation: 'నిర్ధారణ ఇమెయిల్ మళ్లీ పంపండి',
    confirmationResent: 'నిర్ధారణ ఇమెయిల్ మళ్లీ పంపబడింది.',
    back: 'వెనుకకు',
    lightMode: 'లైట్ మోడ్',
    darkMode: 'డార్క్ మోడ్',
  ),
  'mr': OnboardingStrings(
    languagesTitle: 'भाषा',
    languagesLead: 'सुरू करण्यासाठी तुमची आवडती भाषा निवडा.',
    continueLabel: 'पुढे चला',
    welcomeBefore: '',
    welcomeBrandSuffix: ' मध्ये',
    welcomeAfter: 'आपले स्वागत आहे!',
    emailOrPhone: 'ईमेल किंवा फोन नंबर',
    password: 'पासवर्ड',
    forgotPassword: 'पासवर्ड विसरलात?',
    logIn: 'लॉग इन करा',
    or: 'किंवा',
    continueWithGoogle: 'Google सह पुढे चला',
    waitingForGoogle: 'Google ची वाट पाहत आहे…',
    noAccount: 'खाते नाही?',
    signUp: 'साइन अप करा',
    guest: 'अतिथी म्हणून साइन इन करा',
    enterEmailOrPhone: 'तुमचा ईमेल किंवा फोन नंबर टाका.',
    badEmail: 'हा ईमेल पत्ता योग्य वाटत नाही.',
    phoneUnavailable: 'फोनने साइन इन अजून उपलब्ध नाही — कृपया तुमचा ईमेल वापरा.',
    enterPassword: 'तुमचा पासवर्ड टाका.',
    showPassword: 'पासवर्ड दाखवा',
    hidePassword: 'पासवर्ड लपवा',
    resendConfirmation: 'पुष्टीकरण ईमेल पुन्हा पाठवा',
    confirmationResent: 'पुष्टीकरण ईमेल पुन्हा पाठवला.',
    back: 'मागे',
    lightMode: 'लाइट मोड',
    darkMode: 'डार्क मोड',
  ),
};
