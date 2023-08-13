"""
Generates JSON format question-answer pairs and instructions for a Python file
Requirements:
[req01] The `DatasetGenerator` class shall:
        a. Parse a Python file along with a list of questions to produce JSON-formatted question-answer pairs and instructions.
        b. Add the produced question-answer pairs to its `qa_list` attribute.
        c. Append the generated instructions to the `instruct_list` attribute.
        d. Handle exceptions that might arise during the loading of the language model.
        e. Use the `generate` method to generate and provide the `qa_list` and `instruct_list`.
        f. Utilize the `get_model` function to load a specified language model based on a configuration file.
        g. Deploy the loaded language model to generate answers to the questions.
        h. Handle exceptions that may arise during the generation of answers.
        i. Process questions that relate to a file, function, class, or method.
        j. Generate a response for the purpose of a variable when the question type corresponds to this and `use_llm` is set to True.
        k. Produce answers for all questions present in the supplied list, appending the responses to both `qa_list` and `instruct_list`.
        l. Utilize the `clean_and_get_unique_elements` method to cleanse an input string and provide a string of unique elements.
        m. Use the `add_to_list` method to add a generated response to a list.
        n. Obtain a response from the language model by using the `get_response_from_llm` method when `use_llm` is True.
        o. Handle any exceptions that may arise during the response generation from the language model.
        p. Incorporate the file summary into the context for generating the instruction list if the `use_summary` attribute is set to True.
[req02] The `get_python_datasets` function shall:
        a. Construct an instance of the `DatasetGenerator` class.
        b. Invoke the `generate` method of the `DatasetGenerator` instance.
        c. Return the `qa_list` and `instruct_list` produced by the `DatasetGenerator` instance.
"""
import re
import os
import sys
import json
import logging
import yaml
import random
from typing import List, Dict

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s', 
    level=logging.INFO)
logger = logging.getLogger(__name__)

class DatasetGenerator:
    """
    A class used to generate JSON formatted dictionary outputs for a Python 
    file.
    Attributes:
        file_path (str): The path to the Python file.
        file_details (Dict): A dictionary containing details of the Python
            file.
        base_name (str): The base name of the Python file.
        questions (List): A list of questions for which responses are to be
            generated.
        qa_list (List): A list to store the generated question-answer pairs.
        instruct_list (List): A list to store the generated instructions.
        question_mapping (Dict): A dictionary mapping question types to their
            corresponding keys in the file details.
        use_llm (bool): A flag indicating whether to use a language model for
            generating responses.
        llm (AutoModelForCausalLM): The language model to be used for
            generating responses.
    Methods:
        clean_and_get_unique_elements(input_str: str) -> str: Cleans an input 
            string and returns a string of unique elements.
        add_to_list(list_to_update: List[Dict], query: str, response: str,
            additional_field=None) -> List[Dict]: Adds a response to a list.
        get_response_from_llm(query: str, context: str) -> str: Gets a 
            response from the language model.
        get_variable_purpose(question_id: str, question_text: str, base_name:
            str, name: str, info: Dict, context: str, variable_type: str) -> 
                None: Processes questions related to the purpose of a variable.
        process_question(question_id: str, query: str, context: str, info) -> 
            None: Processes a question and adds the generated response to the
            qa_list and instruct_list.
        process_file_question(question_id: str, question_text: str) -> None:
            Processes questions related to a file.
        process_func_class_question(question_type: str, question_id: str, 
            question_text: str) -> None: Processes questions related to a 
            function or class.
        generate() -> Tuple[List[Dict], List[Dict]]: Generates responses for
            all the questions and returns the qa_list and instruct_list.
    """
    def __init__(self, file_path: str, file_details: Dict, base_name: str, questions: List[Dict], use_llm: bool, use_summary: bool, llm, prompt):
        self.file_path = file_path
        self.file_details = file_details
        self.base_name = base_name
        self.questions = questions
        self.qa_list = []
        self.instruct_list = []
        self.question_mapping = {
            'file': 'file',
            'function': 'functions',
            'class': 'classes',
            'method': 'classes'
        }
        self.use_llm = use_llm
        self.llm = llm
        self.prompt = prompt
        # if use_llm = false or llm equil to none then set use_llm to false and llm to none
        if not self.use_llm or self.llm is None:
            self.use_llm = False
            self.llm = None
        self.use_summary = use_summary

    @staticmethod
    def clean_and_get_unique_elements(input_str: str) -> str:
        cleaned_elements = set(re.sub(r'[^\w\-_>\s:/.]', '', element.strip())
                               for element in re.sub(r'\s+', ' ', input_str).split(','))
        return ', '.join(cleaned_elements)

    @staticmethod
    def add_to_list(list_to_update: List[Dict], query: str, response: str, additional_field=None) -> List[Dict]:
        if response and response.strip() and response != 'None':
            list_to_update.append(
                {'instruction': query, 'input' : additional_field, 'output': response}
                if additional_field else
                {'question': query, 'answer': response}
            )
        return list_to_update

    def get_response_from_llm(self, query: str, context: str) -> str:
        response = ''
        if not self.llm:
            logger.error('AI model not available.')
            return response
        try:
            prompt = self.prompt.format(context=context, query=query)
            logging.info(f'Query: {query}')
            response = self.llm(prompt)
            logging.info(f'Response: {response}')
        except:
            logger.error('Failed to generate model response')
        return response

    def process_items(self, question_type: str, question_id: str, question_text: str, base_name: str, name: str, info: Dict, context: str, item_type: str) -> None:
        if info[item_type]:
            items = [item.strip() for item in self.clean_and_get_unique_elements(str(info[item_type])).split(',') if item]
            itemstring = ', '.join(items)
            query = question_text.format(filename=base_name, **{f'{question_type.split("_")[0]}_name': name, f'{question_type.split("_")[0]}_variables': itemstring})
            self.process_question(question_type, question_id, query, context, info)

    def process_question(self, question_type: str, question_id: str, query: str, context: str, info: Dict) -> None:
        if question_id.endswith('code_graph'):
            response = info.get(question_id, {})
        else:
            response = self.get_response_from_llm(query, context) if self.use_llm and question_id.endswith('purpose') else self.clean_and_get_unique_elements(str(info.get(question_id, '')))
        if response and response != 'None':
            response_str = str(response)
            response_str = response_str.strip()
            if response_str:
                self.qa_list.append({'question': query, 'answer': response_str})
                if question_type == 'file' and self.use_summary:
                    context = info['file_summary']
                self.instruct_list.append({'instruction': query, 'input': context, 'output': response_str})

    def process_question_type(self, question_type: str, question_id: str, question_text: str) -> None:
        if question_type == 'file':
            query = question_text.format(filename=self.base_name)
            context = self.file_details['file_info']['file_code']
            info = self.file_details['file_info']
            self.process_question(question_type, question_id, query, context, info)
        elif question_type == 'method':  
            for class_name, class_info in self.file_details['classes'].items():
                for key, method_info in class_info.items():
                    if key.startswith('class_method_'):
                        method_name = key[len('class_method_'):]
                        context = method_info['method_code']
                        mapping = {'class_name': class_name, 'method_name': method_name}
                        query = question_text.format(filename=self.base_name, **mapping)
                        self.process_question(question_type, question_id, query, context, method_info)
        else:
            for name, info in self.file_details[self.question_mapping[question_type]].items():
                context = info[f'{question_type}_code']
                mapping = {f'{question_type}_name': name}
                if question_id == f'{question_type}_variable_purpose' and self.use_llm:
                    self.process_items(question_type, question_id, question_text, self.base_name, name, info, context, f'{question_type}_variables')
                elif question_id != f'{question_type}_variable_purpose':
                    query = question_text.format(filename=self.base_name, **mapping)
                    self.process_question(question_type, question_id, query, context, info)

    def generate(self) -> tuple[List[Dict], List[Dict]]:
        for question in self.questions:
            question_id = question['id']
            question_text = question['text']
            question_type = question['type']
            self.process_question_type(question_type, question_id, question_text)
        return self.qa_list, self.instruct_list

def get_python_datasets(file_path: str, file_details: Dict, base_name: str, questions: List[Dict], llm, prompt, use_llm: bool, use_summary: bool) -> tuple[List[Dict], List[Dict]]:
    """
    Extract information from a Python file and return it in JSON format.
    Args:
        file_path (str): The path to the Python file.
        file_details (Dict): The details of the file.
        base_name (str): The base name.
        questions (List[Dict]): The list of questions.
        use_llm (bool): Whether to use the language model.
        user_config (dict): User-provided model configurations.
    Returns:
        Tuple[List[Dict], List[Dict]]: Extracted information in JSON format.
    """
    generator = DatasetGenerator(file_path, file_details, base_name, questions, use_llm, use_summary, llm, prompt)
    return generator.generate()
