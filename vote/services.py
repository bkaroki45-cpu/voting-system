from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction

from .models import Vote


VOTE_CONFIRMATION_MESSAGE = (
    "Your vote has been successfully recorded in the school election system."
)


class VoteSubmissionError(Exception):
    pass


def send_sms(phone, message):
    if not phone:
        return False

    try:
        import africastalking
    except ImportError:
        return False

    username = getattr(settings, "AFRICASTALKING_USERNAME", "sandbox")
    api_key = getattr(settings, "AFRICASTALKING_API_KEY", None)
    sender_id = getattr(settings, "AFRICASTALKING_SENDER_ID", None)

    if not api_key:
        return False

    africastalking.initialize(username, api_key)
    sms = africastalking.SMS

    try:
        if sender_id:
            sms.send(message, [phone], sender_id=sender_id)
        else:
            sms.send(message, [phone])
    except Exception:
        return False

    return True


def send_email(to_email, subject, message):
    if not to_email:
        return False

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)

    if not from_email:
        return False

    try:
        send_mail(subject, message, from_email, [to_email], fail_silently=True)
    except Exception:
        return False

    return True


def submit_vote(candidate, user=None, phone=None, send_notifications=True):
    if not candidate:
        raise VoteSubmissionError("Candidate is required.")

    if not user and not phone:
        raise VoteSubmissionError("A user or phone number is required.")

    position = candidate.position

    if Vote.has_voted(user=user, phone=phone, position=position):
        raise VoteSubmissionError("Already voted for this position.")

    try:
        with transaction.atomic():
            vote = Vote.objects.create(
                user=user,
                phone=phone,
                position=position,
                candidate=candidate,
            )
    except IntegrityError as exc:
        raise VoteSubmissionError("Already voted for this position.") from exc

    if send_notifications:
        send_vote_confirmation(user=user, phone=phone)

    return vote


def send_vote_confirmation(user=None, phone=None):
    send_sms(phone, VOTE_CONFIRMATION_MESSAGE)

    email = getattr(user, "email", None)
    if email:
        send_email(
            email,
            "Vote Confirmation",
            VOTE_CONFIRMATION_MESSAGE,
        )


def send_results_email(to_email, results_message):
    return send_email(
        to_email,
        "School Election Results",
        results_message,
    )


def speak(text):
    try:
        import pyttsx3
    except ImportError:
        return False

    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return True
    except RuntimeError:
        return False


def listen(timeout=8, phrase_time_limit=6):
    try:
        import speech_recognition as sr
    except ImportError:
        return ""

    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(
            source,
            timeout=timeout,
            phrase_time_limit=phrase_time_limit,
        )

    try:
        return recognizer.recognize_google(audio).strip().lower()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        return ""


def match_candidate(spoken_text, candidates):
    spoken_text = (spoken_text or "").strip().lower()
    if not spoken_text:
        return None

    words_to_numbers = {
        "one": 1,
        "first": 1,
        "two": 2,
        "second": 2,
        "three": 3,
        "third": 3,
        "four": 4,
        "fourth": 4,
        "five": 5,
        "fifth": 5,
        "six": 6,
        "sixth": 6,
        "seven": 7,
        "seventh": 7,
        "eight": 8,
        "eighth": 8,
        "nine": 9,
        "ninth": 9,
        "ten": 10,
        "tenth": 10,
    }

    selected_number = None
    if spoken_text.isdigit():
        selected_number = int(spoken_text)
    else:
        for word, number in words_to_numbers.items():
            if word in spoken_text.split():
                selected_number = number
                break

    if selected_number and 1 <= selected_number <= len(candidates):
        return candidates[selected_number - 1]

    for candidate in candidates:
        if candidate.name.lower() in spoken_text:
            return candidate

    return None
