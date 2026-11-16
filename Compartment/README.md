# Create a compartment using the OCI Console Hands-on Lab

## Goal

Create one empty compartment for all resources in the following OCITestDriveBudapest labs. Allow approximately 5–10 minutes. Use this guide **or** the [Terraform path](terraform/README.md) to create it.

## 1. Confirm access and collect your values

1. Sign in to the OCI Console in the tenancy provided by your instructor.
2. Confirm that your account can create compartments under the designated parent. Your instructor must arrange compartment management permissions and the resource permissions needed by later labs; this exercise creates no IAM policies.
3. Choose the values below. Use your assigned attendee suffix in the name to avoid collisions.

| Field | Example / instruction |
| --- | --- |
| Parent compartment | Tenancy root, or the existing parent assigned by the instructor |
| Name | `OCITestDriveBudapest` |
| Description | `Resource container for the OCITestDriveBudapest hands-on labs` |
| Optional free-form tag | `Project = OCITestDriveBudapest` |

Use a name of 1–100 characters containing letters, numbers, periods, hyphens, or underscores. Keep the description between 1 and 400 characters. The name must be unique within its parent. Avoid confidential information in names, descriptions, and tags.

## 2. Open the parent compartment

1. Open the navigation menu.
2. Select **Identity & Security**.
3. Under **Identity**, select **Compartments**.
4. For a compartment directly under the tenancy root, choose **Create compartment** from the compartment list. For a nested compartment, first open the designated parent's details, then choose **Create compartment**.

## 3. Create the compartment

1. Enter your **Name** and **Description** from step 1.
2. Verify **Parent compartment** carefully. Select the instructor-designated parent if necessary.
3. Optionally add the free-form tag shown above. Follow any tagging requirements imposed by your tenancy.
4. Select **Create compartment**.
5. Open the new compartment and wait for its lifecycle state to become **Active**. Refresh if needed.

## 4. Record and verify the result

1. Check its name and parent on the compartment details page.
2. Find **OCID** and select **Copy**. Record this as the **lab compartment OCID**.
3. Confirm you created only the compartment. No networking or compute resources are created by this exercise.
4. In the next lab, select this compartment on every applicable resource creation form. Allow a short propagation delay if it does not immediately appear in a selector, then refresh.

**Success:** one Active compartment exists under the intended parent, and you have its OCID.

## 5. Keep it for the remaining labs

Leave this compartment in place throughout the training. Later labs will create their resources inside it.

If you later switch to Terraform, follow the import instructions in the [Terraform guide](terraform/README.md); do not try to create the same compartment again.

## 6. Optional cleanup after all labs

1. Remove the resources created by the later labs first, preferably using the same tools and Terraform states that created them.
2. Check for remaining resources across regions and any child compartments. The compartment must be empty before deletion; remove any policies attached to it as part of cleanup.
3. Return to **Identity & Security → Compartments** and open the lab compartment.
4. Use its **Delete** action and complete the Console confirmation. Deletion can take time.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Cannot see the parent or create a compartment | Verify tenancy, parent, and IAM permissions with the instructor. |
| Name already exists | Use a different attendee suffix; do not modify another attendee's compartment. |
| Cannot create resources in the new compartment | Creating a compartment does not grant resource permissions; ask the instructor to check access. |
| Cannot delete the compartment | Remove remaining resources, attached policies, and child compartments; inspect all regions used in the training. |

## Oracle references

- [Creating a compartment](https://docs.oracle.com/en-us/iaas/Content/Identity/compartments/To_create_a_compartment.htm)
- [Deleting a compartment](https://docs.oracle.com/en-us/iaas/Content/Identity/compartments/To_delete_a_compartment.htm)
