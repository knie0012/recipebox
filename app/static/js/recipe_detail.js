"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const favoriteButton = document.getElementById(
        "family-favorite-button"
    );

    const ratingContainer = document.getElementById(
        "rating-stars"
    );

    const ratingStars = Array.from(
        document.querySelectorAll(".rating-star")
    );

    const averageRatingValue = document.getElementById(
        "average-rating-value"
    );

    const averageRatingStars = document.getElementById(
        "average-rating-stars"
    );

    const ratingCount = document.getElementById(
        "rating-count"
    );

    const userRatingText = document.getElementById(
        "user-rating-text"
    );

    const statusElement = document.getElementById(
        "family-card-status"
    );

    /*
     * Prevent errors if this JavaScript is included on a page
     * that does not contain the Family card.
     */
    if (
        !favoriteButton ||
        !ratingContainer ||
        ratingStars.length === 0
    ) {
        return;
    }

    let selectedRating = null;
    let statusTimeout = null;

    const selectedButton = ratingStars.find(
        (button) =>
            button.getAttribute("aria-pressed") === "true"
    );

    if (selectedButton) {
        selectedRating = Number(
            selectedButton.dataset.rating
        );
    }


    function showStatus(message, type = "success") {
        if (!statusElement) {
            return;
        }

        window.clearTimeout(statusTimeout);

        statusElement.textContent = message;
        statusElement.classList.remove(
            "is-success",
            "is-error",
            "is-visible"
        );

        statusElement.classList.add(
            type === "error"
                ? "is-error"
                : "is-success"
        );

        /*
         * Force the browser to register the initial state
         * before applying the visible class.
         */
        void statusElement.offsetWidth;

        statusElement.classList.add("is-visible");

        statusTimeout = window.setTimeout(() => {
            statusElement.classList.remove("is-visible");
        }, 2500);
    }


    async function readJsonResponse(response) {
        let data;

        try {
            data = await response.json();
        } catch {
            throw new Error(
                "The server returned an invalid response."
            );
        }

        if (!response.ok) {
            throw new Error(
                data.error ||
                data.message ||
                "The request could not be completed."
            );
        }

        return data;
    }


    function paintUserStars(rating) {
        ratingStars.forEach((button) => {
            const starValue = Number(
                button.dataset.rating
            );

            const icon = button.querySelector("i");

            if (!icon) {
                return;
            }

            const shouldFill =
                rating !== null &&
                starValue <= rating;

            icon.classList.toggle(
                "bi-star-fill",
                shouldFill
            );

            icon.classList.toggle(
                "bi-star",
                !shouldFill
            );
        });
    }


    function paintAverageStars(average) {
        if (!averageRatingStars) {
            return;
        }

        const roundedAverage = Math.round(
            Number(average) || 0
        );

        const icons = averageRatingStars.querySelectorAll(
            "i"
        );

        icons.forEach((icon, index) => {
            const shouldFill =
                index + 1 <= roundedAverage;

            icon.classList.toggle(
                "bi-star-fill",
                shouldFill
            );

            icon.classList.toggle(
                "bi-star",
                !shouldFill
            );
        });

        averageRatingStars.dataset.averageRating =
            String(average || 0);
    }


    function restoreSelectedRating() {
        paintUserStars(selectedRating);
    }


    function setRatingButtonsDisabled(disabled) {
        ratingStars.forEach((button) => {
            button.disabled = disabled;
        });
    }


    function updateRatingCount(count) {
        const numericCount = Number(count);

        if (numericCount === 0) {
            ratingCount.textContent =
                "Not yet rated";
        } else if (numericCount === 1) {
            ratingCount.textContent =
                "Rated by 1 family member";
        } else {
            ratingCount.textContent =
                `Rated by ${numericCount} family members`;
        }
    }


    function updateSelectedRatingAccessibility() {
        ratingStars.forEach((button) => {
            const starValue = Number(
                button.dataset.rating
            );

            button.setAttribute(
                "aria-pressed",
                starValue === selectedRating
                    ? "true"
                    : "false"
            );
        });
    }


    async function saveRating(rating) {
        const recipeId =
            ratingContainer.dataset.recipeId;

        setRatingButtonsDisabled(true);

        try {
            const response = await fetch(
                `/recipebox/${recipeId}/rating`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json",
                        "Accept":
                            "application/json",
                    },
                    body: JSON.stringify({
                        rating: rating,
                    }),
                }
            );

            const data =
                await readJsonResponse(response);

            selectedRating = Number(
                data.user_rating
            );

            const average = Number(
                data.average_rating
            );

            const count = Number(
                data.rating_count
            );

            paintUserStars(selectedRating);
            updateSelectedRatingAccessibility();

            averageRatingValue.textContent =
                average.toFixed(1);

            paintAverageStars(average);
            updateRatingCount(count);

            userRatingText.textContent =
                `You rated this ${selectedRating} / 10`;

            showStatus("Rating saved.");
        } catch (error) {
            restoreSelectedRating();

            showStatus(
                error.message ||
                "Unable to save rating.",
                "error"
            );

            console.error(
                "Rating request failed:",
                error
            );
        } finally {
            setRatingButtonsDisabled(false);
        }
    }


    ratingStars.forEach((button) => {
        button.addEventListener("mouseenter", () => {
            paintUserStars(
                Number(button.dataset.rating)
            );
        });

        button.addEventListener("focus", () => {
            paintUserStars(
                Number(button.dataset.rating)
            );
        });

        button.addEventListener("click", () => {
            saveRating(
                Number(button.dataset.rating)
            );
        });
    });


    ratingContainer.addEventListener(
        "mouseleave",
        restoreSelectedRating
    );


    ratingContainer.addEventListener(
        "focusout",
        (event) => {
            if (
                !ratingContainer.contains(
                    event.relatedTarget
                )
            ) {
                restoreSelectedRating();
            }
        }
    );


    favoriteButton.addEventListener(
        "click",
        async () => {
            const recipeId =
                favoriteButton.dataset.recipeId;

            const currentValue =
                favoriteButton.getAttribute(
                    "aria-pressed"
                ) === "true";

            favoriteButton.disabled = true;

            try {
                const response = await fetch(
                    `/recipebox/${recipeId}/family-favorite`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json",
                            "Accept":
                                "application/json",
                        },
                        body: JSON.stringify({
                            is_family_favorite:
                                !currentValue,
                        }),
                    }
                );

                const data =
                    await readJsonResponse(response);

                const isFavorite = Boolean(
                    data.is_family_favorite
                );

                const icon =
                    favoriteButton.querySelector("i");

                favoriteButton.setAttribute(
                    "aria-pressed",
                    isFavorite
                        ? "true"
                        : "false"
                );

                favoriteButton.classList.toggle(
                    "is-favorite",
                    isFavorite
                );

                if (icon) {
                    icon.classList.toggle(
                        "bi-heart-fill",
                        isFavorite
                    );

                    icon.classList.toggle(
                        "bi-heart",
                        !isFavorite
                    );
                }

                /*
                 * Restart the pop animation each time.
                 */
                favoriteButton.classList.remove(
                    "favorite-pop"
                );

                void favoriteButton.offsetWidth;

                favoriteButton.classList.add(
                    "favorite-pop"
                );

                showStatus(
                    isFavorite
                        ? "Added to Family Favorites."
                        : "Removed from Family Favorites."
                );
            } catch (error) {
                showStatus(
                    error.message ||
                    "Unable to update Family Favorite.",
                    "error"
                );

                console.error(
                    "Favorite request failed:",
                    error
                );
            } finally {
                favoriteButton.disabled = false;
            }
        }
    );


    favoriteButton.addEventListener(
        "animationend",
        () => {
            favoriteButton.classList.remove(
                "favorite-pop"
            );
        }
    );
});
