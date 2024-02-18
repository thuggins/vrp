import argparse
import itertools
import math
import os
import sys
import time

import pandas as pd


class Driver:
    def __init__(self):
        self.loads = []
        self.driveHours = 0
        self.isScheduling = True


class RouteTime:
    def __init__(
        self,
        loadNumber,
        currentDropoffToNextDropoff,
        dropoffToHome,
    ):
        """
        Initialize the object with load number, dropoff distances and the total distance to home.

        Args:
        load_number (int): The load identifier.
        current_dropoff_to_next_dropoff (float): The distance from the current dropoff to the next dropoff location.
        dropoff_to_home (float): The distance from the dropoff location to the home.
        """
        self.loadNumber = loadNumber
        self.currentDropoffToNextDropoff = currentDropoffToNextDropoff
        self.dropoffToHome = dropoffToHome
        self.currentDropoffToNextDropoffToHome = (
            currentDropoffToNextDropoff + dropoffToHome
        )


def calculateHours(routes):
    """
    Calculate the total travel time in hours based on the given routes.

    Args:
    routes (list): List of tuples representing source and destination coordinates.

    Returns:
    float: Total travel time in hours.
    """
    total_minutes = 0
    for route in routes:
        source, destination = route
        total_minutes += math.sqrt(
            (destination[0] - source[0]) ** 2 + (destination[1] - source[1]) ** 2
        )
    return total_minutes / 60


def findSchedulingDriver(drivers):
    """
    Find the first driver who is available for scheduling.

    Args:
    drivers (list): List of driver objects.

    Returns:
    Driver: The first available driver for scheduling, or None if no driver is available.
    """
    for driver in drivers:
        if driver.isScheduling == True:
            return driver
    return None


def buildRouteTimes(df):
    """
    Build route times for each load using the given dataframe.

    Args:
    df (pandas.DataFrame): The input dataframe containing load and location information.

    Returns:
    list: A list of route times for each load.
    """
    nextRouteTimes = []
    for currentIndex, currentRow in df.iterrows():
        routeTimesForRow = []
        for nextIndex, nextRow in df.iterrows():
            if currentIndex != nextIndex:
                loadNumber = nextRow["loadNumber"]

                currentDropoffToNextDropoff = calculateHours(
                    [
                        (currentRow["dropoff"], nextRow["pickup"]),
                        (nextRow["pickup"], nextRow["dropoff"]),
                    ]
                )

                dropoffToHome = calculateHours(
                    [
                        (nextRow["dropoff"], nextRow["home"]),
                    ]
                )

                routeTime = RouteTime(
                    loadNumber,
                    currentDropoffToNextDropoff,
                    dropoffToHome,
                )

                routeTimesForRow.append(routeTime)

        nextRouteTimes.append(routeTimesForRow)

    return nextRouteTimes


def findNextSchedule(currentLoad, df, driver, loadsScheduled):
    """
    Find the next schedule for a given current load, based on the dataframe, driver, and loads scheduled.

    Args:
    currentLoad (int): The current load number
    df (pandas.DataFrame): The dataframe containing route times
    driver (Driver): The driver object containing drive hours
    loadsScheduled (list): The list of loads already scheduled

    Returns:
    Schedule: The next schedule for the given current load, or None if the driver's drive hours exceed 12
    """
    currentRow = df.loc[df["loadNumber"] == currentLoad].iloc[0]

    nextSchedules = [
        obj for obj in currentRow["routeTimes"] if obj.loadNumber not in loadsScheduled
    ]

    nextSchedule = min(
        nextSchedules, key=lambda obj: obj.currentDropoffToNextDropoffToHome
    )

    if driver.driveHours + nextSchedule.currentDropoffToNextDropoffToHome > 12:
        return None

    return nextSchedule


def applySchedule(loadsScheduled, driver, loadNumber, hours):
    """
    Add a load to the scheduled list, assign the load to the driver, and increment the driver's drive hours.

    :param loads_scheduled: List of loads already scheduled
    :param driver: Driver object
    :param load_number: Number of the load to be scheduled
    :param hours: Number of hours driven for this load
    """
    loadsScheduled.append(loadNumber)
    driver.loads.append(loadNumber)
    driver.driveHours += hours


def main():
    """
    This function reads a CSV file, performs scheduling, and prints the scheduled loads for each driver.
    """

    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("inputPath", help="Path to the input file")
    args = parser.parse_args()
    inputPath = args.inputPath

    # Read the CSV file into a pandas DataFrame
    df = pd.read_csv(
        inputPath,
        header=None,
        delimiter=" ",
        names=["loadNumber", "pickup", "dropoff"],
        converters={1: eval, 2: eval},
        skiprows=1,
    )

    # Set the 'home' column for each row to (0, 0)
    df["home"] = [(0, 0)] * len(df)

    # Calculate the time from home to pickup and pickup to dropoff for each row
    df["homeToDropoff"] = df.apply(
        lambda row: calculateHours(
            [(row["home"], row["pickup"]), (row["pickup"], row["dropoff"])]
        ),
        axis=1,
    )

    # Calculate the time from dropoff back to home for each row
    df["dropoffToHome"] = df.apply(
        lambda row: calculateHours([(row["dropoff"], row["home"])]), axis=1
    )

    # Calculate the route times for each row
    df["routeTimes"] = buildRouteTimes(df)

    # Initialize lists for drivers and scheduled loads
    drivers = []
    loadsScheduled = []

    # Schedule the loads for each driver
    while len(loadsScheduled) < df.shape[0]:
        driver = findSchedulingDriver(drivers)
        if driver == None:
            driver = Driver()
            drivers.append(driver)

        # If the driver has no loads scheduled
        if len(driver.loads) == 0:

            # Find the first schedule for the driver
            firstRoute = (
                df.query("loadNumber not in @loadsScheduled")
                .nsmallest(1, "homeToDropoff")
                .iloc[0]
            )

            # Schedule the first load for the driver
            applySchedule(
                loadsScheduled,
                driver,
                firstRoute["loadNumber"],
                firstRoute["homeToDropoff"],
            )
        # If the driver has loads scheduled
        else:
            # Get the last scheduled load
            lastScheduledLoad = driver.loads[-1]

            # Find the next schedule for the driver's current load
            nextSchedule = findNextSchedule(
                lastScheduledLoad, df, driver, loadsScheduled
            )

            # If no more loads can be scheduled, update driver's drive hours and set scheduling status
            if nextSchedule == None:
                currentRow = df.loc[df["loadNumber"] == lastScheduledLoad].iloc[0]
                driver.driveHours += currentRow["dropoffToHome"]
                driver.isScheduling = False
            else:
                # Schedule the next load for the driver
                applySchedule(
                    loadsScheduled,
                    driver,
                    nextSchedule.loadNumber,
                    nextSchedule.currentDropoffToNextDropoff,
                )

    # Finalize the last driver's schedule
    driver = findSchedulingDriver(drivers)
    lastScheduledLoad = driver.loads[-1]
    currentRow = df.loc[df["loadNumber"] == lastScheduledLoad].iloc[0]
    driver.driveHours += currentRow["dropoffToHome"]
    driver.isScheduling = False

    # Print the scheduled loads for each driver
    for obj in drivers:
        print(obj.loads)


if __name__ == "__main__":
    main()
