import json
import os
import re
import logging
import PyPDF2
from unidecode import unidecode
import sys
from datetime import datetime
# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_config(config_file):
    """
    Loads configuration from a JSON file.
    """
    try:
        with open(config_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        logging.error(f"Configuration file {config_file} not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error(f"Error parsing the configuration file {config_file}.")
        sys.exit(1)


def extract_text_from_pdf(pdf_path):
    """
        Extracts text from a PDF file.

        Args:
        pdf_path (str): The file path to the PDF document.

        Returns:
        str: Extracted text from the PDF.

    """
    text = ''
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text() if page.extract_text() else ''
    return text


def extract_links_from_pdf(pdf_path):
    """
        Extracts hyperlinks from a PDF file.

        Args:
        pdf_path (str): The file path to the PDF document.

        Returns:
        list: A list of extracted hyperlinks.

    """
    links = []
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            if '/Annots' in page:
                annotations = page['/Annots']
                for annotation in annotations:
                    annot_object = annotation.get_object()
                    if '/A' in annot_object and '/URI' in annot_object['/A']:
                        links.append(annot_object['/A']['/URI'])
    return links


def clean_section(header, text, next_header=None):
    """
       Cleans a specific section of text by removing the header and extra newlines.

       Args:
       header (str): The header of the section to clean.
       text (str): The full text containing the section.
       next_header (str, optional): The header of the next section. Defaults to None.

       Returns:
       str: The cleaned text of the specified section.

    """
    pattern = f'{header}[\s\S]*?(?=\n{next_header}|\Z)' if next_header else f'{header}[\s\S]*?(?=\n[A-Z][A-Z ]+\n|\Z)'
    match = re.search(pattern, text)
    if match:
        cleaned_text = re.sub(f'^{header}\s*', '', match.group(0)).strip()
        return re.sub(r'\n+', ' ', cleaned_text)
    return 'Not found'


def extract_gpa(text):
    """
       Extracts the GPA from text.

       Args:
       text (str): The text to extract the GPA from.

       Returns:
       str: The extracted GPA.

    """
    gpa_match = re.search(r'GPA: (\d\.\d+)', text)
    return gpa_match.group(1) if gpa_match else 'Not found'

def calculate_work_experience(text):
    """
    Calculates total work experience in years from the work experience section.

    Args:
    text (str): The text of the work experience section.

    Returns:
    int: Total work experience in years.
    """
    current_year = datetime.now().year
    experience_years = re.findall(r'\b\d{4}\b', text)
    total_years = 0

    for year in experience_years:
        total_years += current_year - int(year)

    # If there are multiple experiences, this will average the years
    if experience_years:
        total_years = total_years // len(experience_years)

    return total_years



def parse_resume(text, links):
    """
    Parses the resume text and extracts various components including work experience in months.

    Args:
    text (str): The full text of the resume.
    links (list): A list of hyperlinks extracted from the resume.

    Returns:
    dict: A dictionary containing parsed resume data.
    """
    text = unidecode(text)

    resume_data = {}

    # Extracting basic information like name, job title, email, and phone
    lines = text.split('\n')
    resume_data['name'] = ' '.join(lines[:2]).strip()
    resume_data['job_title'] = lines[3].strip() if len(lines) > 3 else 'Not found'
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    resume_data['email'] = email_match.group(0) if email_match else 'Not found'
    phone_match = re.search(r'(\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}', text)
    resume_data['phone'] = phone_match.group(0) if phone_match else 'Not found'

    # Extracting social media links
    social_media = {
        'linkedin': 'linkedin.com',
        'facebook': 'facebook.com',
        'twitter': 'twitter.com'
    }

    for platform in social_media:
        resume_data[platform] = 'Not found'

    for link in links:
        for platform, url in social_media.items():
            if url in link and resume_data[platform] == 'Not found':
                resume_data[platform] = link
                break

    # Extracting and cleaning sections like education, skills, etc.
    sections = [('EDUCATION', 'SKILLS'), ('SKILLS', 'CERTIFICATIONS'), ('CERTIFICATIONS', 'CAREER OBJECTIVE'),
                ('WORK EXPERIENCE', 'PROJECTS'), ('PROJECTS', None)]
    for section, next_section in sections:
        section_text = clean_section(section, text, next_section)
        if section == 'EDUCATION':
            section_text = re.sub(r'GPA: \d\.\d+', '', section_text)  # Удаление GPA из образования
        if section == 'CERTIFICATIONS':
            section_text = re.sub(r'CAREER OBJECTIVE[\s\S]*', '',
                                  section_text)  # Удаление лишнего текста из сертификаций
        resume_data[section.lower().replace(' ', '_')] = section_text
        resume_data['gpa'] = extract_gpa(text)

    resume_data['career_objective'] = clean_section('CAREER OBJECTIVE', text, 'WORK EXPERIENCE')

    # New code: Extracting work experience section and calculating total experience in months
    work_experience_section = clean_section('WORK EXPERIENCE', text, 'PROJECTS')
    resume_data['work_experience'] = work_experience_section
    resume_data['seniority'] = calculate_work_experience(work_experience_section)

    return resume_data



def save_to_json(data, json_path):
    """
        Saves data to a JSON file.

        Args:
        data (dict): The data to save.
        json_path (str): The file path to save the JSON data to.

    """
    with open(json_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)


def process_all_pdfs(pdf_directory, json_directory):
    """
        Processes all PDF files in a directory and saves their parsed content as JSON.

        Args:
        pdf_directory (str): The directory containing PDF files.
        json_directory (str): The directory to save JSON files to.

    """
    for filename in os.listdir(pdf_directory):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(pdf_directory, filename)
            json_path = os.path.join(json_directory, os.path.splitext(filename)[0] + '.json')

            extracted_text = extract_text_from_pdf(pdf_path)
            extracted_links = extract_links_from_pdf(pdf_path)
            parsed_resume = parse_resume(extracted_text, extracted_links)
            save_to_json(parsed_resume, json_path)


# pdf_directory = '/home/vadym/Desktop/test/assessment-task/cvs'
# json_directory = '/home/vadym/Desktop/test/assessment-task/cvs/json_cv'
# os.makedirs(json_directory, exist_ok=True)
# process_all_pdfs(pdf_directory, json_directory)

if __name__ == "__main__":
    config = load_config('config.json')

    pdf_directory = config['pdf_dir']
    json_directory = config['json_dir']

    os.makedirs(json_directory, exist_ok=True)
    process_all_pdfs(pdf_directory, json_directory)

