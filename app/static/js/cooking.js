"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const cookingApp = document.getElementById("cooking-app");

    if (!cookingApp) {
        return;
    }

    const recipeId = cookingApp.dataset.recipeId;
    const storageKey = `recipebox-cooking-${recipeId}`;

	
    const ingredientStage = document.getElementById(
        "ingredient-stage"
    );

    const stepStage = document.getElementById(
        "step-stage"
    );

    const beginCookingButton = document.getElementById(
        "begin-cooking-button"
    );

    /*
    Start Over button shown on the ingredient screen.
    */
    const resetButton = document.getElementById(
        "reset-cooking-progress"
    );

    /*
    Start Over button shown while viewing steps.
    */
    const resetStepButton = document.getElementById(
        "reset-step-progress"
    );

    const ingredientCheckboxes = Array.from(
        document.querySelectorAll(
            ".cooking-ingredient-checkbox"
        )
    );

    const referenceCheckboxes = Array.from(
        document.querySelectorAll(
            ".cooking-reference-checkbox"
        )
    );

    const toggleIngredientsButton = document.getElementById(
        "toggle-step-ingredients"
    );

    const stepIngredientPanel = document.getElementById(
        "step-ingredient-panel"
    );

    const ingredientReferenceChevron =
        document.getElementById(
            "ingredient-reference-chevron"
        );

    const cookingSteps = Array.from(
        document.querySelectorAll(".cooking-step")
    );

    const previousButton = document.getElementById(
        "previous-step-button"
    );

    const nextButton = document.getElementById(
        "next-step-button"
    );

    const currentStepNumber = document.getElementById(
        "current-step-number"
    );

    const progressPercent = document.getElementById(
        "step-progress-percent"
    );

    const progressBar = document.getElementById(
        "step-progress-bar"
    );

    const finishedPanel = document.getElementById(
        "cooking-finished-panel"
    );

    const wakeLockButton = document.getElementById(
        "wake-lock-button"
    );

    const wakeLockStatus = document.getElementById(
        "wake-lock-status"
    );
	
	const cookingNavigation = document.querySelector(
	    ".cooking-navigation"
	);

    let currentStepIndex = 0;
    let wakeLockSentinel = null;
    let keepAwakeRequested = true;

	

    function getSavedState() {
        try {
            const savedState = localStorage.getItem(
                storageKey
            );

            if (!savedState) {
                return null;
            }

            return JSON.parse(savedState);
        } catch (error) {
            console.warn(
                "Unable to restore cooking progress:",
                error
            );

            return null;
        }
    }


    function clearSavedState() {
        try {
            localStorage.removeItem(storageKey);
        } catch (error) {
            console.warn(
                "Unable to clear cooking progress:",
                error
            );
        }
    }


    function setIngredientChecked(index, checked) {
        ingredientCheckboxes.forEach(checkbox => {
            if (
                Number(
                    checkbox.dataset.ingredientIndex
                ) === index
            ) {
                checkbox.checked = checked;
            }
        });

        referenceCheckboxes.forEach(checkbox => {
            if (
                Number(
                    checkbox.dataset.ingredientIndex
                ) === index
            ) {
                checkbox.checked = checked;
            }
        });
    }


    function synchronizeIngredientCheckboxes(
        sourceCheckbox
    ) {
        const ingredientIndex = Number(
            sourceCheckbox.dataset.ingredientIndex
        );

        setIngredientChecked(
            ingredientIndex,
            sourceCheckbox.checked
        );

        saveState();
    }


    function saveState() {
        const checkedIngredients =
            ingredientCheckboxes.map(
                checkbox => checkbox.checked
            );

        const state = {
            ingredientStageActive:
                !ingredientStage?.hidden,
            currentStepIndex,
            checkedIngredients,
        };

        try {
            localStorage.setItem(
                storageKey,
                JSON.stringify(state)
            );
        } catch (error) {
            console.warn(
                "Unable to save cooking progress:",
                error
            );
        }
    }


    function showIngredientStage() {
        if (ingredientStage) {
            ingredientStage.hidden = false;
            ingredientStage.classList.add(
                "is-active"
            );
        }

        if (stepStage) {
            stepStage.hidden = true;
            stepStage.classList.remove(
                "is-active"
            );
        }
    }


    function showStepStage() {
        if (ingredientStage) {
            ingredientStage.hidden = true;
            ingredientStage.classList.remove(
                "is-active"
            );
        }

        if (stepStage) {
            stepStage.hidden = false;
            stepStage.classList.add(
                "is-active"
            );
        }

        showStep(currentStepIndex);
    }


	function showStep(
	    stepIndex,
	    preserveNavigationPosition = false
	) {
	    if (!cookingSteps.length) {
	        return;
	    }

	    /*
	    Record where the navigation buttons currently appear
	    on the screen before changing the instruction height.
	    */
	    const previousNavigationTop =
	        preserveNavigationPosition && cookingNavigation
	            ? cookingNavigation.getBoundingClientRect().top
	            : null;

	    currentStepIndex = Math.max(
	        0,
	        Math.min(
	            stepIndex,
	            cookingSteps.length - 1
	        )
	    );

	    cookingSteps.forEach((step, index) => {
	        const isCurrent =
	            index === currentStepIndex;

	        step.hidden = !isCurrent;

	        step.classList.toggle(
	            "is-active",
	            isCurrent
	        );
	    });

	    const displayedStep =
	        currentStepIndex + 1;

	    const percentComplete = Math.round(
	        (
	            currentStepIndex /
	            cookingSteps.length
	        ) * 100
	    );

	    if (currentStepNumber) {
	        currentStepNumber.textContent =
	            displayedStep;
	    }

	    if (progressPercent) {
	        progressPercent.textContent =
	            `${percentComplete}%`;
	    }

	    if (progressBar) {
	        progressBar.style.width =
	            `${percentComplete}%`;
	    }

	    if (previousButton) {
	        previousButton.hidden = false;
	        previousButton.disabled =
	            currentStepIndex === 0;
	    }

	    const isLastStep =
	        currentStepIndex ===
	        cookingSteps.length - 1;

	    if (nextButton) {
	        nextButton.hidden = false;

	        nextButton.innerHTML = isLastStep
	            ? `
	                Finish
	                <i class="bi bi-check-lg"></i>
	              `
	            : `
	                Next
	                <i class="bi bi-arrow-right"></i>
	              `;
	    }

	    if (finishedPanel) {
	        finishedPanel.hidden = true;
	    }

	    saveState();

	    /*
	    After the new instruction is rendered, compensate for
	    its height difference so the navigation remains in the
	    same position on the phone screen.
	    */
	    if (
	        preserveNavigationPosition &&
	        cookingNavigation &&
	        previousNavigationTop !== null
	    ) {
	        requestAnimationFrame(() => {
	            const newNavigationTop =
	                cookingNavigation
	                    .getBoundingClientRect()
	                    .top;

	            const positionChange =
	                newNavigationTop -
	                previousNavigationTop;

	            window.scrollBy({
	                top: positionChange,
	                left: 0,
	                behavior: "instant",
	            });
	        });
	    }
	}


    function finishCooking() {
        cookingSteps.forEach(step => {
            step.hidden = true;
            step.classList.remove(
                "is-active"
            );
        });

        if (previousButton) {
            previousButton.hidden = true;
        }

        if (nextButton) {
            nextButton.hidden = true;
        }

        if (progressPercent) {
            progressPercent.textContent = "100%";
        }

        if (progressBar) {
            progressBar.style.width = "100%";
        }

        if (finishedPanel) {
            finishedPanel.hidden = false;
        }

        /*
        Completing the recipe permanently clears
        the stored session.
        */
        clearSavedState();

        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    }


    function restoreState() {
        const savedState = getSavedState();

        if (!savedState) {
            showIngredientStage();
            return;
        }

        ingredientCheckboxes.forEach(
            (checkbox, index) => {
                const isChecked = Boolean(
                    savedState
                        .checkedIngredients?.[index]
                );

                setIngredientChecked(
                    index,
                    isChecked
                );
            }
        );

        currentStepIndex = Number.isInteger(
            savedState.currentStepIndex
        )
            ? savedState.currentStepIndex
            : 0;

        if (savedState.ingredientStageActive) {
            showIngredientStage();
        } else {
            showStepStage();
        }
    }


    function resetCookingProgress() {
        clearSavedState();

        currentStepIndex = 0;

        ingredientCheckboxes.forEach(
            (checkbox, index) => {
                setIngredientChecked(
                    index,
                    false
                );
            }
        );

        cookingSteps.forEach(
            (step, index) => {
                const isFirstStep =
                    index === 0;

                step.hidden = !isFirstStep;

                step.classList.toggle(
                    "is-active",
                    isFirstStep
                );
            }
        );

        if (stepIngredientPanel) {
            stepIngredientPanel.hidden = true;
        }

        if (toggleIngredientsButton) {
            toggleIngredientsButton.setAttribute(
                "aria-expanded",
                "false"
            );
        }

        if (ingredientReferenceChevron) {
            ingredientReferenceChevron.className =
                "bi bi-chevron-down";
        }

        if (previousButton) {
            previousButton.hidden = false;
            previousButton.disabled = true;
        }

        if (nextButton) {
            nextButton.hidden = false;

            nextButton.innerHTML = `
                Next
                <i class="bi bi-arrow-right"></i>
            `;
        }

        if (finishedPanel) {
            finishedPanel.hidden = true;
        }

        if (currentStepNumber) {
            currentStepNumber.textContent = "1";
        }

        if (progressPercent) {
            progressPercent.textContent = "0%";
        }

        if (progressBar) {
            progressBar.style.width = "0%";
        }

        showIngredientStage();

        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    }


    function confirmStartOver() {
        const confirmed = window.confirm(
            "Start this recipe over? Your checked ingredients and current step will be cleared."
        );

        if (confirmed) {
            resetCookingProgress();
        }
    }


    function toggleIngredientReference() {
        if (
            !stepIngredientPanel ||
            !toggleIngredientsButton
        ) {
            return;
        }

        const isOpening =
            stepIngredientPanel.hidden;

        stepIngredientPanel.hidden =
            !isOpening;

        toggleIngredientsButton.setAttribute(
            "aria-expanded",
            String(isOpening)
        );

        if (ingredientReferenceChevron) {
            ingredientReferenceChevron.className =
                isOpening
                    ? "bi bi-chevron-up"
                    : "bi bi-chevron-down";
        }
    }


    function updateWakeLockStatus(
        message,
        stateClass = ""
    ) {
        if (!wakeLockStatus) {
            return;
        }

        wakeLockStatus.className =
            "wake-lock-status";

        if (stateClass) {
            wakeLockStatus.classList.add(
                stateClass
            );
        }

        const statusText =
            wakeLockStatus.querySelector("span");

        if (statusText) {
            statusText.textContent = message;
        }
    }


    function showWakeLockEnabled() {
        updateWakeLockStatus(
            "Screen will remain awake",
            "is-active"
        );

        if (wakeLockButton) {
            wakeLockButton.disabled = false;

            wakeLockButton.innerHTML = `
                <i class="bi bi-moon"></i>
                Allow Screen Sleep
            `;
        }
    }


    function showWakeLockDisabled() {
        updateWakeLockStatus(
            "Screen may sleep"
        );

        if (wakeLockButton) {
            wakeLockButton.disabled = false;

            wakeLockButton.innerHTML = `
                <i class="bi bi-sun"></i>
                Keep Screen Awake
            `;
        }
    }


    function showWakeLockRetry() {
        updateWakeLockStatus(
            "Tap to keep the screen awake",
            "is-warning"
        );

        if (wakeLockButton) {
            wakeLockButton.disabled = false;

            wakeLockButton.innerHTML = `
                <i class="bi bi-sun"></i>
                Keep Screen Awake
            `;
        }
    }


    async function requestWakeLock() {
        keepAwakeRequested = true;

        if (!("wakeLock" in navigator)) {
            updateWakeLockStatus(
                "Screen awake mode is not supported",
                "is-unavailable"
            );

            if (wakeLockButton) {
                wakeLockButton.disabled = true;
                wakeLockButton.textContent =
                    "Screen awake unavailable";
            }

            return;
        }

        if (
            document.visibilityState !==
            "visible"
        ) {
            showWakeLockRetry();
            return;
        }

        if (wakeLockSentinel) {
            showWakeLockEnabled();
            return;
        }

        try {
            wakeLockSentinel =
                await navigator.wakeLock.request(
                    "screen"
                );

            showWakeLockEnabled();

            wakeLockSentinel.addEventListener(
                "release",
                () => {
                    wakeLockSentinel = null;

                    if (keepAwakeRequested) {
                        showWakeLockRetry();
                    } else {
                        showWakeLockDisabled();
                    }
                }
            );
        } catch (error) {
            wakeLockSentinel = null;

            showWakeLockRetry();

            console.warn(
                "Wake lock request failed:",
                error
            );
        }
    }


    async function releaseWakeLock() {
        keepAwakeRequested = false;

        const existingSentinel =
            wakeLockSentinel;

        wakeLockSentinel = null;

        if (existingSentinel) {
            try {
                await existingSentinel.release();
            } catch (error) {
                console.warn(
                    "Wake lock release failed:",
                    error
                );
            }
        }

        showWakeLockDisabled();
    }


		beginCookingButton?.addEventListener(
			"click",
			() => {
				/*
				Clear the preparation checklist before entering
				the cooking steps so ingredients can be checked
				again as they are actually used.
				*/
				ingredientCheckboxes.forEach(checkbox => {
					checkbox.checked = false;
				});

				referenceCheckboxes.forEach(checkbox => {
					checkbox.checked = false;
				});

				currentStepIndex = 0;

				/*
				Save the cleared ingredient state before
				displaying the first cooking step.
				*/
				saveState();

				showStepStage();
			}
		);


    previousButton?.addEventListener(
        "click",
        () => {
			showStep(
			    currentStepIndex - 1,
			    true
			);
        }
    );


    nextButton?.addEventListener(
        "click",
        () => {
            const isLastStep =
                currentStepIndex ===
                cookingSteps.length - 1;

            if (isLastStep) {
                finishCooking();
                return;
            }

			showStep(
			    currentStepIndex + 1,
			    true
			);
        }
    );


    [
        ...ingredientCheckboxes,
        ...referenceCheckboxes,
    ].forEach(checkbox => {
        checkbox.addEventListener(
            "change",
            () => {
                synchronizeIngredientCheckboxes(
                    checkbox
                );
            }
        );
    });


    /*
    Both Start Over buttons now use the exact
    same confirmation and reset behavior.
    */
    resetButton?.addEventListener(
        "click",
        confirmStartOver
    );

    resetStepButton?.addEventListener(
        "click",
        confirmStartOver
    );


    toggleIngredientsButton?.addEventListener(
        "click",
        toggleIngredientReference
    );


    wakeLockButton?.addEventListener(
        "click",
        async () => {
            if (wakeLockSentinel) {
                await releaseWakeLock();
            } else {
                await requestWakeLock();
            }
        }
    );


    document.addEventListener(
        "visibilitychange",
        () => {
            if (
                document.visibilityState ===
                    "visible" &&
                keepAwakeRequested &&
                !wakeLockSentinel
            ) {
                requestWakeLock();
            }
        }
    );


    window.addEventListener(
        "pagehide",
        () => {
            if (wakeLockSentinel) {
                wakeLockSentinel.release();
            }
        }
    );


    restoreState();
    requestWakeLock();
});