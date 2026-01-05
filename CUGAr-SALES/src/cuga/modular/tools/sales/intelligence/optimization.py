from typing import List, Dict

def optimize_sales_process(data: List[Dict], criteria: Dict) -> List[Dict]:
    """
    Optimize the sales process based on provided criteria.

    Args:
        data (List[Dict]): A list of sales data entries to be optimized.
        criteria (Dict): A dictionary of criteria to optimize against.

    Returns:
        List[Dict]: A list of optimized sales data entries.
    """
    optimized_data = []
    
    for entry in data:
        if meets_criteria(entry, criteria):
            optimized_data.append(entry)
    
    return optimized_data

def meets_criteria(entry: Dict, criteria: Dict) -> bool:
    """
    Check if a sales entry meets the specified criteria.

    Args:
        entry (Dict): A single sales data entry.
        criteria (Dict): A dictionary of criteria to check against.

    Returns:
        bool: True if the entry meets the criteria, False otherwise.
    """
    for key, value in criteria.items():
        if entry.get(key) != value:
            return False
    return True

def personalize_messaging(entry: Dict) -> str:
    """
    Generate personalized messaging for a sales entry.

    Args:
        entry (Dict): A single sales data entry.

    Returns:
        str: A personalized message.
    """
    return f"Hello {entry['contact_name']}, we noticed that you are interested in {entry['product_interest']}."

def analyze_performance(data: List[Dict]) -> Dict:
    """
    Analyze sales performance based on the provided data.

    Args:
        data (List[Dict]): A list of sales data entries.

    Returns:
        Dict: A dictionary containing performance metrics.
    """
    total_sales = sum(entry['sale_amount'] for entry in data)
    total_entries = len(data)
    average_sale = total_sales / total_entries if total_entries > 0 else 0

    return {
        'total_sales': total_sales,
        'average_sale': average_sale,
        'total_entries': total_entries
    }