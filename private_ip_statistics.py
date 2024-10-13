import requests
from bs4 import BeautifulSoup
import re
import csv
import matplotlib.pyplot as plt
from datetime import datetime
import argparse

# Define private IP ranges
def is_private_ip(ip):
    """
    Check if the given IP address is a private IP.
    """
    ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    if not ip_pattern.match(ip):
        return False

    parts = [int(part) for part in ip.split('.')]
    
    if parts[0] == 10:
        return True
    elif parts[0] == 172 and 16 <= parts[1] <= 31:
        return True
    elif parts[0] == 192 and parts[1] == 168:
        return True
    return False

def convert_bandwidth_to_bytes(bandwidth_str):
    """
    Convert bandwidth string (e.g., '12 KB', '2.5 MB', '1 GB', '0.5 TB') to bytes.
    """
    bandwidth_str = bandwidth_str.strip().upper()
    
    match = re.match(r'([\d\.]+)\s*(TB|GB|MB|KB|B)', bandwidth_str)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        
        if unit == 'KB':
            return int(value * 1024)  # KB to bytes
        elif unit == 'MB':
            return int(value * 1024 ** 2)  # MB to bytes
        elif unit == 'GB':
            return int(value * 1024 ** 3)  # GB to bytes
        elif unit == 'TB':
            return int(value * 1024 ** 4)  # TB to bytes
        elif unit == 'B':
            return int(value)  # Already in bytes
    return 0  # If no match, assume 0 bytes

def format_bandwidth(size_in_bytes):
    """
    Convert the total bandwidth in bytes to the most appropriate unit (B, KB, MB, GB, TB).
    """
    if size_in_bytes >= 1024 ** 4:
        return f"{size_in_bytes / (1024 ** 4):.2f} TB"
    elif size_in_bytes >= 1024 ** 3:
        return f"{size_in_bytes / (1024 ** 3):.2f} GB"
    elif size_in_bytes >= 1024 ** 2:
        return f"{size_in_bytes / (1024 ** 2):.2f} MB"
    elif size_in_bytes >= 1024:
        return f"{size_in_bytes / 1024:.2f} KB"
    else:
        return f"{size_in_bytes} B"

def parse_awstats_monthly_page(url):
    """
    Parse the AWStats monthly page and calculate total bandwidth consumed by private IPs.
    """
    total_bandwidth = 0

    # Send a GET request to fetch the AWStats page
    response = requests.get(url)
    response.raise_for_status()  # Ensure the request was successful

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the section containing the "All Hosts" IP and bandwidth data
    table = soup.find('table', {'border': '1'})  # Tables in AWStats typically have a border attribute

    if not table:
        print("Unable to find the data table. Adjust your selector.")
        return total_bandwidth

    # Skip the header rows
    rows = table.find_all('tr')[2:]

    # Iterate through table rows (tr)
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 6:
            continue
        
        ip = cols[0].text.strip()  # First column is the IP address or "Others"
        
        # Check if it's a valid IP address and a private IP
        if not is_private_ip(ip) and ip != 'Others':
            continue

        # Bandwidth is likely the 6th column (after Pages, Hits, and GeoIP columns)
        bandwidth_str = cols[5].text.strip()

        # Convert the bandwidth to bytes
        bandwidth_in_bytes = convert_bandwidth_to_bytes(bandwidth_str)

        # Sum up the bandwidth in bytes
        total_bandwidth += bandwidth_in_bytes

    return total_bandwidth

def fetch_and_save_monthly_data(start_year, start_month, end_year, end_month):
    """
    Fetch and save monthly bandwidth data for the given range of months and years to a CSV file.
    """
    csv_filename = 'monthly_bandwidth_data.csv'
    monthly_bandwidth = {}

    # Iterate over years and months
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if year == start_year and month < start_month:
                continue
            if year == end_year and month > end_month:
                break

            month_str = f"{month:02d}"
            url = f"https://glua.ua.pt/awstats/cgi-bin/awstats.pl?databasebreak=month&month={month_str}&year={year}&config=http&framename=mainright&output=urldetail"
            print(f"Processing {year}-{month_str}...")
            bandwidth_in_bytes = parse_awstats_monthly_page(url)
            
            # Format and print the bandwidth for the current month
            formatted_bandwidth = format_bandwidth(bandwidth_in_bytes)
            print(f"Total bandwidth for {year}-{month_str}: {formatted_bandwidth}")
            
            # Store the bandwidth data
            monthly_bandwidth[f"{year}-{month_str}"] = bandwidth_in_bytes

    # Write to CSV
    with open(csv_filename, 'w', newline='') as csvfile:
        fieldnames = ['Year-Month', 'Bandwidth (Bytes)']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for month, bandwidth in monthly_bandwidth.items():
            writer.writerow({'Year-Month': month, 'Bandwidth (Bytes)': bandwidth})

    return monthly_bandwidth

def create_bandwidth_graph(monthly_bandwidth):
    """
    Create a graph of yearly bandwidth usage based on monthly data.
    """
    # Extract year and month data
    months = list(monthly_bandwidth.keys())
    bandwidths = list(monthly_bandwidth.values())

    # Convert bandwidths to GB for better visualization
    bandwidths_gb = [bw / (1024 ** 3) for bw in bandwidths]

    # Extract years for x-axis labels
    years = [datetime.strptime(month, "%Y-%m").strftime("%Y-%m") for month in months]

    plt.figure(figsize=(12, 6))
    plt.plot(years, bandwidths_gb, marker='o', linestyle='-', color='b')
    plt.xticks(rotation=90)
    plt.xlabel('Year-Month')
    plt.ylabel('Bandwidth (GB)')
    plt.title('Monthly Bandwidth Usage')
    plt.tight_layout()
    plt.savefig('yearly_bandwidth_usage.png')
    plt.show()

if __name__ == '__main__':
    # Define command-line arguments
    parser = argparse.ArgumentParser(description="Fetch and calculate bandwidth usage from AWStats.")
    parser.add_argument('--start_year', type=int, required=True, help='Start year (e.g., 2020)')
    parser.add_argument('--start_month', type=int, required=True, help='Start month (1-12)')
    parser.add_argument('--end_year', type=int, required=True, help='End year (e.g., 2024)')
    parser.add_argument('--end_month', type=int, required=True, help='End month (1-12)')

    # Parse arguments
    args = parser.parse_args()

    # Fetch data and save to CSV
    monthly_bandwidth = fetch_and_save_monthly_data(args.start_year, args.start_month, args.end_year, args.end_month)

    # Create and save the bandwidth usage graph
    create_bandwidth_graph(monthly_bandwidth)
