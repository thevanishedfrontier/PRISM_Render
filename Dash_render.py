#%%
## Author A. Moore
## This point of this program is to scrape publicly available information
## from the PRISM website, and compile it into a an interactive chloropleth map

import plotly.express as px
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.request import urlopen
import json
import dash
from dash import dcc, html, Input, Output, dash_table



# Used to add a column to the data frame based on which decade -
# the county joined
def classify_decade(date_str):
    if date_str == "Not a member":
        return "Not a member"
    try:
        year = int(date_str.split('/')[-1])
        if 1970 <= year < 1980:
            return "70's"
        elif 1980 <= year < 1990:
            return "80's"
        elif 1990 <= year < 2000:
            return "90's"
        elif 2000 <= year < 2010:
            return "2000's"
        elif 2010 <= year < 2020:
            return "2010's"
    except ValueError:
        return None

#Retrieves geojson data from a github link
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    json_counties = json.load(response)

#URL used to scrape county information
URL = 'https://www.prismrisk.gov/members/county/'
r = requests.get(URL)
soup = BeautifulSoup(r.content, 'html.parser')

#Intitialize empty vectors to store relevant information
counties = []
dates = []
county_urls = []

## Loops through the html to find all the relevant county names, join dates, and links to the county page
for tbody in soup.find_all('tbody'):
    county = tbody.find('a').text.strip()
    date = tbody.find('td', class_='subtle').text.strip()
    url = tbody.find('a')['href']
    full_url = 'https://www.prismrisk.gov' + url
    counties.append(county.replace('County', '').strip())
    dates.append(date)
    county_urls.append(full_url)

## Empty vector to store which insurance programs a county participates in
program_participation = []
#%%
## Loops through all the hyperlinks to scrape the relevant program information
for url in county_urls:
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')

    ## finds tbody element
    tbody = soup.find('tbody')

    ## Extracts the relevant text
    if tbody:
        programs = [row.find('td').text for row in tbody.find_all('tr')]
        program_participation.append(programs)


## code to count and store the number of programs a county participates in
number_of_programs = []
for programs in program_participation:
    count = len(programs)
    number_of_programs.append(count)


## Combines the relevant vectors into a data frame for later visualization
data = pd.DataFrame({
    'County': counties,
    'Date': dates,
    'Program Participation': program_participation,
    'Number of Programs': number_of_programs
})

#%%

## Needed to also scrape CA fips data for the chloropleth map
FIPSURL = 'https://www.weather.gov/hnx/cafips'
fr = requests.get(FIPSURL)
fsoup = BeautifulSoup(fr.content, 'html.parser')
td_elements = fsoup.find_all('td', bgcolor="#9DACD7")

## Lists to store counties and fips code
counties = []
fips_codes = []

## Looping over the html
for i in range(0, len(td_elements) - 1, 2):
    county_name = td_elements[i].get_text(strip=True)
    fips_code = td_elements[i + 1].get_text(strip=True)

    ## Prepending the CA State code 06 to three digit county code
    fips_code = '06' + fips_code

    ## Store values
    counties.append(county_name)
    fips_codes.append(fips_code)

## Creating a data frame to store the fips data
fipsdata = pd.DataFrame({
    'counties': counties,
    'fips_code': fips_codes
})


## Sorting the dataframe so that it is also in alphabetical order
fipsdata = fipsdata.sort_values(by='counties', ascending=True).reset_index(drop=True)


## Merging the data frames so they conain all CA counties, their FIPS code, and member counties will have a join date
merged_data = pd.merge(data, fipsdata, left_on='County', right_on='counties', how='right')

## removing an extraneous County column
merged_data = merged_data.drop(columns=['County'])

## Remove blank first row
merged_data.drop(0, axis=0, inplace=True)

## Replace NA values for non-member counties
merged_data['Date'] = merged_data['Date'].fillna('Not a member')
merged_data['Number of Programs'] = merged_data['Number of Programs'].fillna(0)
merged_data['Program Participation'] = merged_data['Program Participation'].fillna('Not a member')

## Adding the decade column for better visualization
merged_data["decade"] = merged_data["Date"].apply(classify_decade)




## Creating the dash app
app = dash.Dash(__name__)
server = app.server

app.layout = html.Div([
    html.H1("Interactive Dashboard of PRISM clients by county"),

    ## Dropdown menu to toggle between decade, and nuber of programs
    html.Label("Select data to display:"),
    dcc.Dropdown(
        id="data-toggle",
        options=[
            {"label": "Decade", "value": "decade"},
            {"label": "Number of Programs", "value": "Number of Programs"}
        ],
        value="decade",  ## Default value
        clearable=False
    ),

    ## Graph to display the choropleth map
    dcc.Graph(
        id="choropleth-map",
        style={"width": "100vw", "height": "100vh"}
    )
])

## Callback to repopulate data when drop town is toggled
@app.callback(
    Output("choropleth-map", "figure"),
    [Input("data-toggle", "value")]
)
def update_map(selected_column):
    ## Change what information is displayed in hover data
    hover_data = {
        "Program Participation": selected_column == "Number of Programs",
        "fips_code": False  ## Exclude fips code from hover data
    }

    ## Generating the chloropleth map
    fig = px.choropleth(
        merged_data,
        geojson=json_counties,
        locations="fips_code",
        color=selected_column,
        scope="usa",
        hover_name="counties",
        hover_data=hover_data
    )

    ## Update bounds to exclude other states
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
    ## Set background to white
        plot_bgcolor="white",
        geo=dict(bgcolor="white")
    )


    return fig

## Run the dash app
if __name__ == "__main__":
    app.run_server(debug=True)
