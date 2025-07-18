🕸️ Web Scraper API
A simple FastAPI application to scrape product data (like name, image, price) from websites.

🚀 Features
Scrape product details using a URL

Interactive Swagger UI

Built with FastAPI and BeautifulSoup

🔧 Setup Instructions
1. Clone the Repository
bash
Copy
Edit
git clone https://github.com/csana004/Deepsolv.git
cd Deepsolv
2. Install Dependencies
Create a virtual environment (optional but recommended):

bash
Copy
Edit
python -m venv venv
venv\Scripts\activate   # On Windows
Then install requirements:

bash
Copy
Edit
pip install -r requirements.txt
3. Run the FastAPI Server
bash
Copy
Edit
uvicorn main:app --reload
main is the name of the Python file (e.g., main.py).
If your file is named differently, adjust accordingly.

🌐 Try it in Your Browser
Once the server is running, open your browser and go to:

arduino
Copy
Edit
http://127.0.0.1:8000/docs
This opens the Swagger UI, where you can:

Click on the /scrape endpoint.

Hit "Try it out".

Enter a product URL like:

arduino
Copy
Edit
https://www.hairoriginals.com/products/remy-human-hair-scrunchie
Click Execute to see the scraped data!

📂 Example Request
Endpoint: POST /scrape
Body:

json
Copy
Edit
{
  "url": "https://www.example.com/product/123"
}
📦 Project Structure
bash
Copy
Edit
Deepsolv/
│
├── main.py           # FastAPI app
├── scraper.py        # Scraping logic
├── database.py       # Optional: for storing data
├── requirements.txt  # Python dependencies
└── README.md         # This file
🧼 To-Do
 Add error handling for invalid URLs

 Add support for more websites

 Store scraped data in a database (MongoDB or SQLite)

