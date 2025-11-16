from jellyfin_apiclient_python import JellyfinClient
import requests
from dotenv import load_dotenv
import os
import json

load_dotenv()


def get_series_from_jelly() -> list[str]:
    client = JellyfinClient()
    client.config.app("series-recom", "0.0.1", "x", "123")
    client.config.data["auth.ssl"] = False

    url = os.getenv("JELLY_URL")
    client.auth.connect_to_address(url)
    client.auth.login(url, os.getenv("JELLY_USERNAME"), os.getenv("JELLY_PASSWORD"))

    data = client.jellyfin.search_media_items(term="", media="Series")

    item_ids = []

    for item in data.get("Items", []):
        if item.get("Type") == "Series":
            item_ids.append(item["Id"])
    
    tmdb_ids = []
    for item_id in item_ids:
        item = client.jellyfin.get_item(item_id)
        tmdb_id = item["ProviderIds"]["Tmdb"]
        tmdb_ids.append(tmdb_id)

    return tmdb_ids


def get_tmdb_headers() -> dict[str, str]:
    token = os.getenv("TMDB_BEARER")

    headers = {"accept": "application/json", "Authorization": f"Bearer {token}"}

    return headers


def get_genre_ids_to_exclude() -> str:
    # get all genres and ids for the ones we want to exclude
    url = "https://api.themoviedb.org/3/genre/tv/list"
    response = requests.get(url, headers=get_tmdb_headers())
    result = response.json()

    genre_to_id = {d["name"]: d["id"] for d in result["genres"]}

    genres_to_exclude = [
        "Animation",
        "Family",
        "Kids",
        "News",
        "Reality",
        "Sci-Fi & Fantasy",
        "Soap",
        "Talk",
        "Western",
    ]

    ids_to_exclude = ",".join([str(genre_to_id[genre]) for genre in genres_to_exclude])

    return ids_to_exclude


def get_relevant_series_ids() -> dict[int, str]:
    # define filters
    params = {
        "with_origin_country": "US",
        "first_air_date.gte": "2025-05-01",
        "sort_by": "popularity.desc",
        "without_genres": get_genre_ids_to_exclude(),
    }

    # query first page to get the total pages
    url = "https://api.themoviedb.org/3/discover/tv"
    params["page"] = 1
    response = requests.get(url, headers=get_tmdb_headers(), params=params)
    data = response.json()
    results_all = data["results"]

    # get the rest of the pages if needed
    if data["total_pages"] > 1:
        for page in range(2, data["total_pages"] + 1):
            url = "https://api.themoviedb.org/3/discover/tv"
            params["page"] = page
            response = requests.get(url, headers=get_tmdb_headers(), params=params)
            data = response.json()
            results_all.extend(data["results"])

    return {d["id"]: d["original_name"] for d in results_all}


def get_details_by_id(series_id: str):
    url = f"https://api.themoviedb.org/3/tv/{series_id}"
    params = {
        "append_to_response": "credits,keywords,recommendations,similar,content_ratings,videos,images,aggregate_credits,reviews"
    }
    response = requests.get(url, headers=get_tmdb_headers(), params=params)
    details = response.json()

    file_path = os.path.join("data/tmdb/details_by_ids", str(series_id) + ".json")
    with open(file_path, "w") as f:
        json.dump(details, f)

    print("Downloaded and saved details for", series_id)

    return


def check_if_series_exists(series_id: str) -> bool:
    file_path = os.path.join("data/tmdb/details_by_ids", str(series_id) + ".json")
    return os.path.exists(file_path)


def main():

    tmdb_ids_watched = get_series_from_jelly()

    tmdb_name_by_id_all = get_relevant_series_ids()
    tmdb_ids_all = list(tmdb_name_by_id_all.keys())

    # combine
    tmdb_ids_to_fetch = tmdb_ids_watched + tmdb_ids_all

    # download details
    for series_id in tmdb_ids_to_fetch:
        if not check_if_series_exists(series_id):
            get_details_by_id(series_id)

    return


if __name__ == "__main__":
    main()
