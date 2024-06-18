import os
import time
from dotenv import load_dotenv
from groq import Groq
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
import streamlit as st

# Function to load and process the documents from a URL
def get_docs_from_url(url):
    loader = WebBaseLoader(url)
    docs = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)
    split_docs = text_splitter.split_documents(docs)
    st.write('Documents Loaded from URL')
    return split_docs

# Function to load and process the documents from an uploaded PDF file
def get_docs(uploaded_file):
    start_time = time.time()
    with open("temp.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())
    loader = PyPDFLoader("temp.pdf")
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=100)
    final_documents = text_splitter.split_documents(documents)
    st.write('Documents Loaded')
    end_time = time.time()
    st.write(f"Time taken to load documents: {end_time - start_time:.2f} seconds")
    os.remove("temp.pdf")  # Clean up the temporary file
    return final_documents

# Function to create vector store
def create_vector_store(docs):
    start_time = time.time()
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={"trust_remote_code": True})
    vectorstore = FAISS.from_documents(docs, embeddings)
    st.write('DB is ready')
    end_time = time.time()
    st.write(f"Time taken to create DB: {end_time - start_time:.2f} seconds")
    return vectorstore

# Function to interact with Groq AI
def chat_groq(messages):
    load_dotenv()
    client = Groq(api_key=os.environ.get('GROQ_API_KEY'))
    response_content = ''
    stream = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=messages,
        max_tokens=1024,
        temperature=1.3,
        stream=True,
    )

    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            response_content += chunk.choices[0].delta.content
    return response_content

# Function to summarize the chat history
def summarize_chat_history(chat_history):
    chat_history_text = " ".join([f"{chat['role']}: {chat['content']}" for chat in chat_history])
    prompt = f"Summarize the following chat history:\n\n{chat_history_text}"
    messages = [{'role': 'system', 'content': 'You are very good at summarizing the chat between User and Assistant'}]
    messages.append({'role': 'user', 'content': prompt})
    summary = chat_groq(messages)
    return summary

# Main function to control the app
def main():
    
    st.set_page_config(page_title='AravindDocuQuery')

    st.title("ArvDocuQuery")

    with st.expander("Instructions"):
        st.write("1. Choose a document source using the radio button.")
        st.write("2. If uploading a PDF, click 'Upload PDF', select your file, and wait for 'Documents Loaded' confirmation.")
        st.write("3. If entering a web URL, enter the URL, click 'Enter Web URL', and wait for 'Documents Loaded from URL' confirmation.")
        st.write("4. After loading documents, click 'Create Vector Store' to process.")
        st.write("5. Enter a question in the text area and submit to interact with the AI chatbot.")
        st.write("6. Click on Generate Chat Summary to get the conversation of the Chat Session")
        st.write("Visit https://aravind-llama3groqchatbot.streamlit.app/ if you want to use the generic chatbot.")

    
    if "docs" not in st.session_state:
        st.session_state.docs = None
    if "vectorstore" not in st.session_state:
        st.session_state.vectorstore = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "user_input" not in st.session_state:
        st.session_state.user_input = ""
    if "current_prompt" not in st.session_state:
        st.session_state.current_prompt = ""
    if "chat_summary" not in st.session_state:
        st.session_state.chat_summary = ""

    st.subheader("Choose document source:")
    option = st.radio("Select one:", ("Upload PDF", "Enter Web URL"))

    if option == "Upload PDF":
        uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
        if uploaded_file is not None:
            if st.session_state.docs is None:
                with st.spinner("Loading documents..."):
                    docs = get_docs(uploaded_file)
                st.session_state.docs = docs

    elif option == "Enter Web URL":
        url = st.text_input("Enter URL", key="url_input")
        if st.session_state.url_input != url:
            st.session_state.url_input = url
            st.session_state.docs = None
        if url and st.session_state.docs is None:
            with st.spinner("Fetching and processing documents from URL..."):
                docs = get_docs_from_url(url)
            st.session_state.docs = docs

    if st.session_state.docs is not None:
        if st.button('Create Vector Store'):
            with st.spinner("Creating vector store..."):
                vectorstore = create_vector_store(st.session_state.docs)
            st.session_state.vectorstore = vectorstore

    if st.session_state.vectorstore is not None:
        retriever = st.session_state.vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})

        def submit():
            user_message = st.session_state.user_input
            if user_message:
                context = retriever.invoke(user_message)
                prompt = f'''
                Answer the user's question based on the latest input provided in the chat history. Ignore
                previous inputs unless they are directly related to the latest question. Provide a generic
                answer if the answer to the user's question is not present in the context by mentioning it
                as general information.

                Context: {context}

                Chat History: {st.session_state.chat_history}

                Latest Question: {user_message}
                '''

                messages = [{'role': 'system', 'content': 'You are a very helpful assistant'}]
                messages.append({'role': 'user', 'content': prompt})

                ai_response = chat_groq(messages)

                # Display the current output prompt
                st.session_state.current_prompt = ai_response
                # st.write(st.session_state.current_prompt)

                # Update chat history
                st.session_state.chat_history.append({'role': 'user', 'content': user_message})
                st.session_state.chat_history.append({'role': 'assistant', 'content': ai_response})

                # Clear the input field
                st.session_state.user_input = ""

        st.text_area("Enter your question:", key="user_input", on_change=submit)

        # Display the current output prompt if available
        if st.session_state.current_prompt:
            st.write(st.session_state.current_prompt)

        # Button to generate chat summary
        if st.button('Generate Chat Summary'):
            st.session_state.chat_summary = summarize_chat_history(st.session_state.chat_history)

        # Display the chat summary if available
        if st.session_state.chat_summary:
            with st.expander("Chat Summary"):
                st.write(st.session_state.chat_summary)

        # Display the last 4 messages in an expander
        with st.expander("Recent Chat History"):
            recent_history = st.session_state.chat_history[-8:][::-1]
            reversed_history = []
            for i in range(0, len(recent_history), 2):
                reversed_history.extend([recent_history[i+1], recent_history[i]])
            for chat in reversed_history:
                st.write(f"{chat['role'].capitalize()}: {chat['content']}")

if __name__ == "__main__":
    main()
