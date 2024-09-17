import speech_recognition as sr
from pydub import AudioSegment
import os
import yt_dlp
from concurrent.futures import ThreadPoolExecutor, as_completed
from groq import Groq
# for hosting on a hosting service use the first option. If hosting locally use the second but remember to set up the env variable.

#APIK = os.environ.get('APIK')
APIK = "api key here"

client = Groq(api_key=APIK)

def ytaudio(url, output_path="youtube_audio.mp3"):
    ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': output_path,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
    }],
    # input your youtube cookie file paths here
    'cookiefile': '',
    #'cookiefile': r'',
}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if os.path.exists(output_path + '.mp3'):
            os.rename(output_path + '.mp3', output_path)
        return output_path
    except Exception as e:
        print(f"Error downloading youtube mp3: {e}")
        return None
# convert into wav
def convertaudio(mp3_file):
    audio = AudioSegment.from_mp3(mp3_file)
    wav_file = mp3_file.rsplit('.', 1)[0] + '.wav'
    audio.export(wav_file, format="wav")
    return wav_file
# cut audio into 30 second segments
def cutaudio(audio_file, segment_length_ms=30000):
    audio = AudioSegment.from_file(audio_file)
    segments = []
    
    for i in range(0, len(audio), segment_length_ms):
        segment = audio[i:i+segment_length_ms]
        segment_file = f"segment_{i//segment_length_ms}.wav"
        segment.export(segment_file, format="wav")
        segments.append(segment_file)
    
    return segments
# upload segments to google for transcription
def transaud(audio_file):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio)
        return audio_file, text
    except sr.UnknownValueError:
        print(f"Unable to transcribe audio in: {audio_file}")
    except sr.RequestError as e:
        print(f"Failed to start Speech Recognition, Restart and try switching networks. {audio_file}; {e}")
    return audio_file, ""
# the prompt, I didnt really attempt to make a good one so tune it to your needs
def aistuff(text):
    system_prompt = {
        "role": "system",
        "content": "You are a precise summarization tool. Your task is to create a detailed, comprehensive summary of the provided text. Follow these guidelines:\n\n1. Summarize only the information present in the given text.\n2. Do not add any external information or your own analysis.\n3. Maintain the original text's key points, main ideas, and important details.\n4. Organize the summary into multiple paragraphs (its required to have at least 5-7) for better readability.\n5. Each paragraph should be 5-7 sentences long.\n6. Use clear, concise language while preserving the essence of the original content.\n7. If the text contains sections or subheadings, reflect this structure in your summary."
    }
    messages = [
        system_prompt,
        {"role": "user", "content": f"Please provide a detailed summary of the following text, adhering strictly to the guidelines provided:\n\n{text}"}
    ]
# you can change the model. personally ive found this model to work best.
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages,
        max_tokens=8192,
        temperature=0.3
    )
    
    return response.choices[0].message.content

def main():
    choice = input("Enter '1' to summarize a local audio file or '2' to download and summarize a Youtube video: ")

    if choice == '1':
        mp3_file = input("Enter the path to your audio file (mp3): ")
        if not os.path.isfile(mp3_file):
            print("Unable to find file.")
            return
    elif choice == '2':
        url = input("Enter the Youtube video URL: ")
        mp3_file = ytaudio(url)
        if not mp3_file or not os.path.isfile(mp3_file):
            print(f"Error downloading from YouTube: {mp3_file}")
            return
    else:
        print("Invalid choice.")
        return

    if not os.path.isfile(mp3_file):
        print(f"Unable to find: {mp3_file}")
        return

    wav_file = convertaudio(mp3_file)
    segments = cutaudio(wav_file)

    print("Transcribing audio...")
    transcriptions = {}
    with ThreadPoolExecutor(max_workers=200) as executor:
        future_to_segment = {executor.submit(transaud, segment): segment for segment in segments}
        for future in as_completed(future_to_segment):
            segment = future_to_segment[future]
            try:
                audio_file, text = future.result()
                transcriptions[audio_file] = text
            except Exception as exc:
                print(f'{segment} generated an exception: {exc}')

    full_transcription = " ".join([transcriptions.get(segment, "") for segment in segments])

    print("Transcription:")
    print(full_transcription)

    print("\nGenerating summary...")
    summary = aistuff(full_transcription)
    print("\nSummary:")
    print(summary)

    os.remove(wav_file)
    for segment in segments:
        os.remove(segment)
    if choice == '2':
        os.remove(mp3_file)

if __name__ == "__main__":
    main()
